#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scan_current_project import DEFAULT_RULES_FILE, scan_project


DEFAULT_USER_GLOBS = [
    {
        "path_glob": "Core/Src/app_*.c",
        "classification": "user_owned",
        "generated_by": "user",
        "editable_strategy": "free_edit",
        "notes": ["Application layer source file. Safe for free edits."],
    },
    {
        "path_glob": "Core/Inc/app_*.h",
        "classification": "user_owned",
        "generated_by": "user",
        "editable_strategy": "free_edit",
        "notes": ["Application layer header file. Safe for free edits."],
    },
    {
        "path_glob": "Core/Src/bsp_*.c",
        "classification": "user_owned",
        "generated_by": "user",
        "editable_strategy": "free_edit",
        "notes": ["Board support source file. Safe for free edits."],
    },
    {
        "path_glob": "Core/Inc/bsp_*.h",
        "classification": "user_owned",
        "generated_by": "user",
        "editable_strategy": "free_edit",
        "notes": ["Board support header file. Safe for free edits."],
    },
]


RULE_NOTES_BY_PATH = {
    "Core/Src/main.c": [
        "Edit USER CODE blocks only.",
        "Do not change SystemClock_Config or MX init order.",
    ],
    "Core/Src/stm32f4xx_it.c": [
        "Prefer USER CODE blocks or HAL callbacks only.",
    ],
    "Core/Inc/stm32f4xx_it.h": [
        "Edit USER CODE blocks only.",
    ],
    "Core/Src/stm32f4xx_hal_msp.c": [
        "Avoid manual edits unless the task directly requires MSP changes.",
    ],
    "Core/Inc/stm32f4xx_hal_conf.h": [
        "Avoid manual edits to HAL config by default.",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate stm32-cubemx-rules.json for a CubeMX HAL project.")
    parser.add_argument("project_root", help="Path to the STM32CubeMX project root.")
    parser.add_argument("--ioc", default="", help="Optional explicit .ioc path.")
    parser.add_argument("--output", default="", help="Optional explicit output path. Defaults to <project_root>/stm32-cubemx-rules.json.")
    parser.add_argument("--stdout", action="store_true", help="Print JSON to stdout instead of writing the file.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing rules file.")
    return parser.parse_args()


def build_rule_entry(path: str, management: Dict[str, Any]) -> Dict[str, Any]:
    entry = {
        "path_glob": path,
        "classification": management.get("classification", "user_owned"),
        "generated_by": management.get("generated_by", "user"),
        "editable_strategy": management.get("editable_strategy", "free_edit"),
        "notes": [],
    }

    if entry["classification"] == "cubemx_project_manifest":
        entry["notes"] = ["Edit this file in CubeMX only."]
    elif path in RULE_NOTES_BY_PATH:
        entry["notes"] = RULE_NOTES_BY_PATH[path]
    else:
        generated_notes = management.get("notes", [])
        if isinstance(generated_notes, list):
            entry["notes"] = [str(item) for item in generated_notes if str(item).strip()]

    return entry


def build_rules(scan: Dict[str, Any]) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    management_by_file = scan.get("management_by_file", {})

    ordered_paths: List[str] = []
    for abs_path, management in management_by_file.items():
        rel = str(management.get("path", "")).strip()
        if not rel:
            continue
        if rel not in ordered_paths:
            ordered_paths.append(rel)

    for rel in sorted(ordered_paths, key=lambda item: (0 if item.endswith(".ioc") else 1, item)):
        management = next(
            item for item in management_by_file.values()
            if str(item.get("path", "")).strip() == rel
        )
        files.append(build_rule_entry(rel, management))

    files.extend(DEFAULT_USER_GLOBS)
    return {"files": files}


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    output_path = Path(args.output).resolve() if args.output else (project_root / DEFAULT_RULES_FILE)

    scan = scan_project(project_root, explicit_ioc=args.ioc)
    status = scan.get("status", {})
    if not bool(status.get("is_cubemx_project")):
        raise SystemExit(f"Not a CubeMX HAL project: {project_root}")

    if output_path.exists() and not args.force and not args.stdout:
        raise SystemExit(f"Rules file already exists: {output_path}. Use --force to overwrite.")

    payload = build_rules(scan)
    content = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.stdout:
        print(content)
        return 0

    output_path.write_text(content, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
