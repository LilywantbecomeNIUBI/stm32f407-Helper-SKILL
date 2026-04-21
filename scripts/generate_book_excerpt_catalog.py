#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MATERIALS_ROOT = Path(os.environ.get("STM32F407_MATERIALS_ROOT", REPO_ROOT / "materials"))
DEFAULT_TEXTBOOK_ROOT = DEFAULT_MATERIALS_ROOT / "textbook"
DEFAULT_OUTPUT = REPO_ROOT / "assets" / "book_excerpt_catalog.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate book_excerpt_catalog.json from textbook-side *.index.json files."
    )
    parser.add_argument("--materials-root", default="", help="Materials root. Defaults to STM32F407_MATERIALS_ROOT or ./materials.")
    parser.add_argument("--textbook-root", default="", help="Override textbook root. Defaults to <materials-root>/textbook.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output book_excerpt_catalog.json path.")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def normalize_entry(entry: Dict[str, Any], source_file: Path, textbook_root: Path) -> Dict[str, Any]:
    chapter = str(entry.get("chapter") or entry.get("title") or "").strip()
    if not chapter:
        raise ValueError(f"Missing chapter/title in {source_file}")

    source_pdf = str(entry.get("source_pdf", "")).strip()
    if source_pdf:
        source_pdf = source_pdf.replace("\\", "/")
    else:
        pdf_candidates = sorted(source_file.parent.glob("*.pdf"))
        source_pdf = str(pdf_candidates[0].relative_to(textbook_root)).replace("\\", "/") if pdf_candidates else ""

    result = {
        "id": str(entry.get("id") or f"{source_file.stem}:{chapter}").strip(),
        "book_id": str(entry.get("book_id", "")).strip(),
        "chapter": chapter,
        "category": normalize_string_list(entry.get("category")),
        "keywords": normalize_string_list(entry.get("keywords")),
        "summary": str(entry.get("summary", "")).strip(),
        "excerpt": str(entry.get("excerpt", "")).strip(),
        "source_pdf": source_pdf,
        "page_range": str(entry.get("page_range", "")).strip(),
        "key_pages": [int(item) for item in entry.get("key_pages", []) if str(item).strip().isdigit()],
    }

    if not result["summary"] and result["excerpt"]:
        result["summary"] = result["excerpt"][:80].strip()

    return result


def collect_entries(textbook_root: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    for manifest_path in sorted(textbook_root.rglob("*.index.json")):
        payload = load_json(manifest_path)
        if isinstance(payload, dict):
            items = payload.get("entries", [])
            common_book_id = str(payload.get("book_id", "")).strip()
            common_categories = normalize_string_list(payload.get("category"))
            common_pdf = str(payload.get("source_pdf", "")).strip()
        elif isinstance(payload, list):
            items = payload
            common_book_id = ""
            common_categories = []
            common_pdf = ""
        else:
            raise ValueError(f"Unsupported manifest shape: {manifest_path}")

        if not isinstance(items, list):
            raise ValueError(f"'entries' must be a list in {manifest_path}")

        for raw_entry in items:
            if not isinstance(raw_entry, dict):
                continue
            merged = dict(raw_entry)
            if common_book_id and not merged.get("book_id"):
                merged["book_id"] = common_book_id
            if common_categories:
                current_categories = normalize_string_list(merged.get("category"))
                merged["category"] = current_categories + [item for item in common_categories if item not in current_categories]
            if common_pdf and not merged.get("source_pdf"):
                merged["source_pdf"] = common_pdf
            entries.append(normalize_entry(merged, manifest_path, textbook_root))

    entries.sort(key=lambda item: (item.get("source_pdf", ""), item.get("chapter", ""), item.get("id", "")))
    return entries


def main() -> int:
    args = parse_args()
    materials_root = Path(args.materials_root).resolve() if args.materials_root else DEFAULT_MATERIALS_ROOT.resolve()
    textbook_root = Path(args.textbook_root).resolve() if args.textbook_root else (materials_root / "textbook")
    output_path = Path(args.output).resolve()

    if not textbook_root.exists():
        raise FileNotFoundError(f"Textbook root not found: {textbook_root}")

    entries = collect_entries(textbook_root)
    output_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(entries)} entries -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
