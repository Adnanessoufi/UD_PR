"""One-command preparation check. Never prints credentials or sends model requests."""

import argparse
import importlib.util
import json
from pathlib import Path
import httpx
from app.services.model_gateway import describe
from app.services.openai_service import AIServiceError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", help="Optional local API URL, e.g. http://127.0.0.1:8001")
    args = parser.parse_args()
    names = ("fastapi", "pydantic", "openai", "pymupdf", "docx", "PIL", "moviepy", "httpx")
    report = {
        "dependencies": {name: importlib.util.find_spec(name) is not None for name in names},
        "api_calls_to_model": 0,
        "credentials": "Configuration is inspected; credential validity is not tested.",
    }
    try:
        report["provider"] = describe()
    except AIServiceError as exc:
        report["provider_error"] = str(exc)
    root = Path(__file__).resolve().parents[2]
    report["source_prompts_present"] = (root / "app/prompts/combined.txt").is_file()
    report["evaluation_cases_present"] = (root / "evals/factuality.json").is_file()
    if args.server:
        try:
            response = httpx.get(args.server.rstrip("/") + "/api/system/capabilities", timeout=10)
            report["server_status"] = response.status_code
            if response.is_success:
                report["server_capabilities"] = response.json()
        except httpx.HTTPError:
            report["server_error"] = "Could not reach the API."
    print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
