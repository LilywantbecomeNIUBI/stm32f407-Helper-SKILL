#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from parse_ioc import find_ioc_file, parse_ioc


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_RULES_FILE = "stm32-cubemx-rules.json"

HANDLE_RE = re.compile(r"\b([a-z]?(?:adc|can|crc|dac|dcmi|dfsdm|dma2d?|eth|fmc|fsmc|i2c|i2s|irda|lptim|ltdc|nand|nor|pcd|qspi|rng|rtc|sai|sd|sdio|smartcard|smbus|spi|tim|uart|usart|wwdg|hcd)[a-z0-9_]*)\b")
MX_INIT_RE = re.compile(r"\b(MX_[A-Za-z0-9_]+_Init)\s*\(")
CALLBACK_RE = re.compile(r"\b(HAL_[A-Za-z0-9_]+Callback)\s*\(")
IRQ_RE = re.compile(r"\b([A-Za-z0-9_]+IRQHandler)\s*\(")
USER_CODE_BEGIN_RE = re.compile(r"USER CODE BEGIN ([A-Za-z0-9_ ]+)")
USER_CODE_END_RE = re.compile(r"USER CODE END ([A-Za-z0-9_ ]+)")

GENERATED_FILE_NAMES = {
    "main.c",
    "main.h",
    "stm32f4xx_it.c",
    "stm32f4xx_it.h",
    "stm32f4xx_hal_msp.c",
    "stm32f4xx_hal_conf.h",
    "gpio.c",
    "gpio.h",
    "dma.c",
    "dma.h",
    "adc.c",
    "adc.h",
    "usart.c",
    "usart.h",
    "tim.c",
    "tim.h",
    "spi.c",
    "spi.h",
    "i2c.c",
    "i2c.h",
    "can.c",
    "can.h",
    "rtc.c",
    "rtc.h",
    "fatfs.c",
    "fatfs.h",
    "freertos.c",
    "freertos.h",
    "usb_otg.c",
    "usb_otg.h",
    "fsmc.c",
    "fsmc.h",
    "sdio.c",
    "sdio.h",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan current STM32CubeMX HAL project state.")
    parser.add_argument("root", nargs="?", default=str(REPO_ROOT), help="Project root to scan.")
    parser.add_argument("--ioc", default="", help="Optional explicit .ioc path.")
    parser.add_argument("--format", dest="output_format", choices=["json", "text"], default="json", help="Output format.")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def choose_project_root(scan_root: Path, ioc_path: Path | None) -> Path:
    if ioc_path is not None:
        return ioc_path.parent
    return scan_root


def path_matches_glob(path: Path, project_root: Path, pattern: str) -> bool:
    rel = path.relative_to(project_root).as_posix()
    return path.match(pattern) or Path(rel).match(pattern)


def load_project_rules(project_root: Path) -> Dict[str, Any]:
    rules_path = project_root / DEFAULT_RULES_FILE
    if not rules_path.exists():
        return {"rules_path": "", "rules": []}
    payload = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Project rules must be a JSON object: {rules_path}")
    rules = payload.get("files", [])
    if not isinstance(rules, list):
        raise ValueError(f"'files' must be a list in: {rules_path}")
    return {"rules_path": str(rules_path), "rules": rules}


def find_file_candidates(project_root: Path) -> Dict[str, List[Path]]:
    files = {
        "main_c": sorted(project_root.rglob("main.c")),
        "it_c": sorted(project_root.rglob("stm32f4xx_it.c")),
        "it_h": sorted(project_root.rglob("stm32f4xx_it.h")),
        "hal_msp_c": sorted(project_root.rglob("stm32f4xx_hal_msp.c")),
        "hal_conf_h": sorted(project_root.rglob("stm32f4xx_hal_conf.h")),
    }
    return files


def detect_user_code_sections(text: str) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    active: Dict[str, Any] | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        begin_match = USER_CODE_BEGIN_RE.search(line)
        if begin_match:
            active = {"label": begin_match.group(1).strip(), "begin_line": lineno}
            continue
        end_match = USER_CODE_END_RE.search(line)
        if end_match and active is not None:
            active["end_line"] = lineno
            sections.append(active)
            active = None
    return sections


def classify_generated_file(path: Path, project_root: Path, text: str) -> Dict[str, Any]:
    rel = path.relative_to(project_root).as_posix()
    user_sections = detect_user_code_sections(text)
    name = path.name.lower()

    classification = "user_owned"
    editable_strategy = "free_edit"
    generated_by = "user"
    notes: List[str] = []

    if path.suffix.lower() == ".ioc":
        classification = "cubemx_project_manifest"
        editable_strategy = "edit_in_cubemx_only"
        generated_by = "cubemx"
        notes.append("The .ioc file is the source of truth for CubeMX configuration.")
    elif "/* USER CODE BEGIN" in text or name in GENERATED_FILE_NAMES:
        classification = "cubemx_generated"
        editable_strategy = "user_sections_only" if user_sections else "avoid_manual_edit"
        generated_by = "cubemx"
        if user_sections:
            notes.append("Prefer editing only inside USER CODE BEGIN/END blocks.")
        else:
            notes.append("No USER CODE blocks were detected; avoid editing unless the user explicitly approves it.")
    elif rel.startswith("Core/Inc/") or rel.startswith("Core/Src/"):
        classification = "project_source"
        editable_strategy = "free_edit"
    elif rel.startswith("Drivers/") or rel.startswith("Middlewares/"):
        classification = "vendor_or_framework"
        editable_strategy = "avoid_manual_edit"
        notes.append("Prefer not to patch vendor or framework code unless the task directly requires it.")

    return {
        "path": rel,
        "classification": classification,
        "generated_by": generated_by,
        "editable_strategy": editable_strategy,
        "user_code_sections": user_sections,
        "notes": notes,
    }


def apply_rule_overrides(base: Dict[str, Any], path: Path, project_root: Path, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    rel = path.relative_to(project_root).as_posix()
    merged = dict(base)
    for rule in rules:
        pattern = str(rule.get("path_glob", "")).strip()
        if not pattern or not path_matches_glob(path, project_root, pattern):
            continue
        for key in ("classification", "generated_by", "editable_strategy", "notes"):
            if key in rule:
                merged[key] = rule[key]
        if "user_code_sections" in rule:
            merged["user_code_sections"] = rule["user_code_sections"]
        merged.setdefault("matched_rules", []).append(pattern)
    merged["path"] = rel
    return merged


def extract_symbols_from_file(path: Path) -> Dict[str, List[str]]:
    text = read_text(path)
    mx_inits = dedupe(MX_INIT_RE.findall(text))
    callbacks = dedupe(CALLBACK_RE.findall(text))
    irqs = dedupe(IRQ_RE.findall(text))
    handles = dedupe(
        match
        for match in HANDLE_RE.findall(text)
        if any(match.startswith(prefix) for prefix in ("h", "g"))
    )
    return {
        "mx_inits": mx_inits,
        "callbacks": callbacks,
        "irqs": irqs,
        "handles": handles,
    }


def scan_project(scan_root: Path, explicit_ioc: str = "") -> Dict[str, Any]:
    ioc_path: Path | None = None
    ioc_summary: Dict[str, Any] | None = None
    try:
        ioc_path = find_ioc_file(explicit_ioc, scan_root)
        ioc_summary = parse_ioc(ioc_path)
    except FileNotFoundError:
        ioc_path = None
        ioc_summary = None

    project_root = choose_project_root(scan_root, ioc_path)
    candidates = find_file_candidates(project_root)
    rules_payload = load_project_rules(project_root)
    project_rules = rules_payload["rules"]

    symbol_map: Dict[str, Dict[str, List[str]]] = {}
    management_map: Dict[str, Dict[str, Any]] = {}
    aggregate = {
        "mx_inits": [],
        "callbacks": [],
        "irqs": [],
        "handles": [],
    }

    for group_name, paths in candidates.items():
        for path in paths:
            text = read_text(path)
            symbols = extract_symbols_from_file(path)
            symbol_map[str(path)] = symbols
            management = classify_generated_file(path, project_root, text)
            management_map[str(path)] = apply_rule_overrides(management, path, project_root, project_rules)
            for key in aggregate:
                aggregate[key].extend(symbols[key])

    if ioc_path is not None:
        management_map[str(ioc_path)] = apply_rule_overrides(
            classify_generated_file(ioc_path, project_root, ""),
            ioc_path,
            project_root,
            project_rules,
        )

    for key in aggregate:
        aggregate[key] = dedupe(sorted(aggregate[key]))

    management_summary = {
        "cubemx_project_manifest": 0,
        "cubemx_generated": 0,
        "project_source": 0,
        "user_owned": 0,
        "vendor_or_framework": 0,
    }
    editable_summary = {
        "edit_in_cubemx_only": 0,
        "user_sections_only": 0,
        "avoid_manual_edit": 0,
        "free_edit": 0,
    }
    for item in management_map.values():
        management_summary[item["classification"]] = management_summary.get(item["classification"], 0) + 1
        editable_summary[item["editable_strategy"]] = editable_summary.get(item["editable_strategy"], 0) + 1

    return {
        "scan_root": str(scan_root),
        "project_root": str(project_root),
        "ioc_found": ioc_path is not None,
        "ioc_path": str(ioc_path) if ioc_path else "",
        "ioc_summary": ioc_summary,
        "project_rules": {
            "rules_path": rules_payload["rules_path"],
            "rule_count": len(project_rules),
            "needs_generation": bool(ioc_path is not None and len(project_rules) == 0),
            "suggested_path": str(project_root / DEFAULT_RULES_FILE),
            "suggested_command": (
                f'python scripts/generate_cubemx_rules.py "{project_root}"'
                if ioc_path is not None and len(project_rules) == 0
                else ""
            ),
        },
        "files": {
            name: [str(path) for path in paths]
            for name, paths in candidates.items()
        },
        "symbols": aggregate,
        "symbols_by_file": symbol_map,
        "management_by_file": management_map,
        "management_summary": management_summary,
        "editable_summary": editable_summary,
        "status": {
            "is_cubemx_project": ioc_path is not None,
            "has_main_c": bool(candidates["main_c"]),
            "has_it_c": bool(candidates["it_c"]),
            "has_hal_msp_c": bool(candidates["hal_msp_c"]),
            "has_hal_conf_h": bool(candidates["hal_conf_h"]),
            "mx_init_count": len(aggregate["mx_inits"]),
            "callback_count": len(aggregate["callbacks"]),
            "irq_handler_count": len(aggregate["irqs"]),
            "handle_count": len(aggregate["handles"]),
        },
    }


def format_text(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    status = result["status"]
    lines.append(f"scan_root: {result['scan_root']}")
    lines.append(f"project_root: {result['project_root']}")
    lines.append(f"is_cubemx_project: {status['is_cubemx_project']}")
    if result.get("ioc_path"):
        lines.append(f"ioc_path: {result['ioc_path']}")
    if result.get("project_rules", {}).get("rules_path"):
        lines.append(f"project_rules: {result['project_rules']['rules_path']}")
    lines.append("")

    lines.append("files:")
    for key, paths in result.get("files", {}).items():
        if not paths:
            continue
        lines.append(f"- {key}:")
        for path in paths[:5]:
            lines.append(f"  - {path}")
    lines.append("")

    lines.append("mx_inits:")
    for item in result["symbols"]["mx_inits"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("callbacks:")
    for item in result["symbols"]["callbacks"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("irq_handlers:")
    for item in result["symbols"]["irqs"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("handles:")
    for item in result["symbols"]["handles"]:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("management_summary:")
    for key, value in result.get("management_summary", {}).items():
        lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("editable_summary:")
    for key, value in result.get("editable_summary", {}).items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    result = scan_project(Path(args.root).resolve(), explicit_ioc=args.ioc)
    if args.output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
