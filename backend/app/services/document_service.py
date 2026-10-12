"""Extract source text while preserving PDF page boundaries."""

from pathlib import Path

import pymupdf
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


class EmptyPdfError(Exception):
    """A readable PDF contains no selectable text."""


class EmptyDocxError(Exception):
    """A readable Word document contains no body or table text."""


def _word_blocks(container):
    for block in container.iter_inner_content():
        if isinstance(block, Paragraph):
            if block.text.strip():
                yield block.text
        elif isinstance(block, Table):
            for row in block.rows:
                cells = []
                seen = set()
                for cell in row.cells:
                    # Horizontally merged cells appear more than once in a row.
                    if cell._tc in seen:
                        continue
                    seen.add(cell._tc)
                    cells.append(" / ".join(_word_blocks(cell)))
                if any(cell.strip() for cell in cells):
                    yield "\t".join(cells)


def extract_document(path: Path, filename: str, file_type: str) -> dict:
    if file_type == "pdf":
        with pymupdf.open(path) as document:
            pages = [
                {"page": index + 1, "text": page.get_text()} for index, page in enumerate(document)
            ]
            if not any(page["text"].strip() for page in pages):
                raise EmptyPdfError()
            return {
                "filename": filename,
                "file_type": "pdf",
                "page_count": len(pages),
                "pages": pages,
            }

    document = Document(path)
    text = "\n".join(_word_blocks(document))
    if not text.strip():
        raise EmptyDocxError()
    return {
        "filename": filename,
        "file_type": "docx",
        "page_count": None,
        "text": text,
    }
