"""Bounded public HTTPS news/feed intake; no AI calls during collection."""

import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
from html import unescape
import ipaddress
import json
from pathlib import Path
import re
import socket
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode
from uuid import uuid4
from xml.etree import ElementTree
import httpx
from app.services.campaign_service import read_json, write_json
from app.services.openai_service import AIServiceError

STORAGE = Path(__file__).resolve().parents[2] / "storage"
MAX_BODY = 2 * 1024 * 1024
INBOX_LOCK = asyncio.Lock()


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.startswith("utm_") and k not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), "")
    )


async def validate_url(url: str) -> str:
    try:
        url = canonical_url(url)
        parts = urlsplit(url)
    except ValueError as exc:
        raise AIServiceError("Enter a valid public HTTPS URL.", 422) from exc
    if len(url) > 2048:
        raise AIServiceError("Source URL is too long.", 422)
    try:
        port = parts.port
    except ValueError as exc:
        raise AIServiceError("Enter a public HTTPS URL.", 422) from exc
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
        or port not in (None, 443)
    ):
        raise AIServiceError("News intake accepts public HTTPS URLs without credentials.", 422)
    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo, parts.hostname, 443, type=socket.SOCK_STREAM
        )
    except OSError as exc:
        raise AIServiceError("The source hostname could not be resolved.", 422) from exc
    if not addresses or any(
        not ipaddress.ip_address(a[4][0]).is_global or ipaddress.ip_address(a[4][0]).is_multicast
        for a in addresses
    ):
        raise AIServiceError("Private and local network sources are not allowed.", 422)
    return url


async def fetch(url: str) -> tuple[str, str]:
    async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
        for _ in range(5):
            url = await validate_url(url)
            try:
                async with client.stream(
                    "GET", url, headers={"User-Agent": "UD-PR-Studio/1.0"}
                ) as response:
                    if response.is_redirect:
                        target = response.headers.get("location")
                        if not target:
                            break
                        url = urljoin(url, target)
                        continue
                    if response.status_code != 200:
                        raise AIServiceError(
                            f"The news source returned HTTP {response.status_code}.", 422
                        )
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_BODY:
                            raise AIServiceError("The source exceeds the 2 MB intake limit.", 413)
                    return url, bytes(body).decode(response.encoding or "utf-8", errors="replace")
            except httpx.HTTPError as exc:
                raise AIServiceError(
                    "Could not fetch the source. Try another public news URL.", 502
                ) from exc
    raise AIServiceError("The source redirected too many times.", 422)


class ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.title = []
        self.blocks = []
        self.current = None
        self.skip = 0
        self.description = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append(tag)
        if tag in {"script", "style", "nav", "footer", "header", "aside", "noscript"}:
            self.skip += 1
        if tag in {"p", "h1", "h2", "h3"} and not self.skip:
            self.current = []
        if tag == "meta" and attrs.get("name", "").lower() == "description":
            self.description = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag in {"p", "h1", "h2", "h3"} and self.current is not None:
            text = " ".join("".join(self.current).split())
            if len(text) > 15:
                self.blocks.append(text)
            self.current = None
        if tag in {"script", "style", "nav", "footer", "header", "aside", "noscript"} and self.skip:
            self.skip -= 1
        if tag in self.stack:
            self.stack = self.stack[: len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if "title" in self.stack and "head" in self.stack:
            self.title.append(data)
        if not self.skip and self.current is not None:
            self.current.append(data)


def parse_article(html: str) -> tuple[str, str]:
    parser = ArticleParser()
    parser.feed(html)
    title = " ".join("".join(parser.title).split())[:180]
    blocks = list(dict.fromkeys(parser.blocks))
    text = "\n\n".join(blocks)
    if len(text) < 200:
        raise AIServiceError(
            "This page has too little readable article text. Try the original article URL.", 422
        )
    return title or blocks[0][:140], text[:100000]


def parse_feed(xml: str, feed_url: str) -> list[dict]:
    # CDATA and comments are inert text; embedded article HTML may contain a doctype.
    declarations = re.sub(r"<!\[CDATA\[.*?\]\]>|<!--.*?-->", "", xml, flags=re.S)
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", declarations, re.I):
        raise AIServiceError(
            "Feeds with document types or entity declarations are not supported.", 422
        )
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise AIServiceError("The URL did not return a readable RSS or Atom feed.", 422) from exc
    entries = [e for e in root.iter() if e.tag.split("}")[-1] in {"item", "entry"}]
    result = []
    for entry in entries[:60]:
        children = {e.tag.split("}")[-1]: e for e in entry}

        def value(key):
            return "".join(children[key].itertext()).strip() if key in children else ""

        link = value("link")
        for child in entry:
            if (
                child.tag.split("}")[-1] == "link"
                and child.attrib.get("rel", "alternate") == "alternate"
            ):
                link = child.attrib.get("href") or "".join(child.itertext()).strip()
                break
        if not link:
            continue
        try:
            link = canonical_url(urljoin(feed_url, link))
        except ValueError:
            continue
        if urlsplit(link).scheme != "https":
            continue
        result.append(
            {
                "id": uuid4().hex,
                "url": link,
                "title": value("title")[:200] or link,
                "summary": re.sub(
                    r"<[^>]+>", "", unescape(value("description") or value("summary"))
                )[:500],
                "published": value("pubDate") or value("published") or value("updated"),
                "feed_url": feed_url,
            }
        )
    if not result:
        raise AIServiceError("The feed contains no usable HTTPS article links.", 422)
    return result


def inbox() -> dict:
    return read_json(STORAGE, "news_inbox.json", {"feeds": [], "items": [], "refreshed_at": None})


async def refresh_feeds(urls: list[str]) -> dict:
    async with INBOX_LOCK:
        current = inbox()
        items = {item["url"]: item for item in reversed(current["items"])}
        errors = []
        added = 0
        for url in dict.fromkeys(urls):
            try:
                final_url, xml = await fetch(url)
                for item in parse_feed(xml, final_url):
                    if item["url"] not in items:
                        items[item["url"]] = item
                        added += 1
                    else:
                        items[item["url"]] = {**item, "id": items[item["url"]]["id"]}
            except AIServiceError as exc:
                errors.append({"url": url, "message": str(exc)})
        data = {
            "feeds": list(dict.fromkeys(urls)),
            "items": list(items.values())[-200:][::-1],
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }
        STORAGE.mkdir(parents=True, exist_ok=True)
        write_json(STORAGE, "news_inbox.json", data)
        return {**data, "added": added, "errors": errors}


async def import_article(url: str) -> dict:
    final_url, html = await fetch(url)
    title, text = parse_article(html)
    # Reuse collected text, without merging distinct articles or regenerating a cached draft.
    for folder in STORAGE.iterdir() if STORAGE.exists() else []:
        if (
            folder.is_dir()
            and read_json(folder, "extracted_text.json", {}).get("source_url") == final_url
            and read_json(folder, "extracted_text.json", {}).get("text") == text
        ):
            stored = read_json(folder, "extracted_text.json", {})
            if stored.get("filename") != title:
                stored["filename"] = title
                write_json(folder, "extracted_text.json", stored)
            return {
                "run_id": folder.name,
                "filename": title,
                "file_type": "news",
                "page_count": None,
                "status": "ready",
                "cached": (folder / "master_content.json").is_file(),
            }
    folder = STORAGE / str(uuid4())
    folder.mkdir(parents=True, exist_ok=False)
    write_json(
        folder,
        "extracted_text.json",
        {
            "filename": title,
            "file_type": "news",
            "page_count": None,
            "source_url": final_url,
            "text": text,
        },
    )
    return {
        "run_id": folder.name,
        "filename": title,
        "file_type": "news",
        "page_count": None,
        "status": "ready",
        "cached": False,
    }
