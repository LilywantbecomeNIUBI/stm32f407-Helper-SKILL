#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_MATERIALS_ROOT = Path(os.environ.get("STM32F407_MATERIALS_ROOT", REPO_ROOT / "materials"))

ROOT_DIR = DEFAULT_MATERIALS_ROOT / "examples"
OUTPUT_PATH = REPO_ROOT / "assets" / "example_catalog.json"

README_CANDIDATES = ("readme.txt", "README.txt", "Readme.txt")
MAX_SUMMARY_CHARS = 120
MAX_DESCRIPTION_CHARS = 220
MAX_KEYWORDS = 12

ZH_EXPERIMENT_NAME = "\u5b9e\u9a8c\u540d\u79f0"
ZH_EXPERIMENT_PURPOSE = "\u5b9e\u9a8c\u76ee\u7684"
ZH_EXPERIMENT_PHENOMENON = "\u5b9e\u9a8c\u73b0\u8c61"

SECTION_ALIASES = {
    ZH_EXPERIMENT_NAME: "title",
    ZH_EXPERIMENT_PURPOSE: "purpose",
    ZH_EXPERIMENT_PHENOMENON: "phenomenon",
}
SECTION_ORDER = ("title", "purpose", "phenomenon")

NON_TARGET_HEADERS = {
    "\u5b9e\u9a8c\u7b80\u4ecb",
    "\u7b80\u4ecb",
    "\u8bf4\u660e",
    "\u6982\u8ff0",
    "\u5b9e\u9a8c\u5e73\u53f0",
    "\u786c\u4ef6\u8d44\u6e90\u53ca\u5f15\u811a\u5206\u914d",
    "\u6ce8\u610f\u4e8b\u9879",
    "\u529f\u80fd\u8bf4\u660e",
}

IGNORE_EXACT_LINES = {
    "\u65e0",
    "\u6682\u65e0",
    "\u7565",
}
IGNORE_PREFIXES = (
    "\u516c\u53f8\u540d\u79f0",
    "\u7535\u8bdd\u53f7\u7801",
    "\u4f20\u771f\u53f7\u7801",
    "\u7535\u5b50\u90ae\u7bb1",
    "\u516c\u53f8\u7f51\u5740",
    "\u8d2d\u4e70\u5730\u5740",
    "\u8d2d\u4e70\u94fe\u63a5",
    "\u6280\u672f\u8bba\u575b",
    "\u6700\u65b0\u8d44\u6599",
    "\u5728\u7ebf\u89c6\u9891",
    "B \u7ad9\u89c6\u9891",
    "\u516c\u4f17\u53f7",
    "\u516c \u4f17 \u53f7",
    "\u6296 \u97f3",
    "\u6296\u97f3",
)
IGNORE_SUBSTRINGS_COMPACT = (
    "tmall.com",
    "bilibili.com",
    "weixin.qq.com",
    "taobao.com",
    "douyin.com",
    "openedv.com",
    "yuanzige.com",
    "zhengdianyuanzi",
)
IGNORE_LINE_PATTERNS = [
    re.compile(r"^[=\-_*#~\s]+$"),
    re.compile(r"^[A-Z]{2,}\d*\s*[（(].*[)）]\s*:\s*[A-Z]+\d+", re.IGNORECASE),
    re.compile(r"^[A-Z]{2,}\d*\s*:\s*[A-Z]+\d+", re.IGNORECASE),
    re.compile(r"\bP[A-I]\d{1,2}\b", re.IGNORECASE),
]
STOPWORDS = {
    "experiment",
    "hal",
    "stm32",
    "f4",
    "f407",
    "user",
    "main",
    "readme",
    "core",
    "src",
    "inc",
    "title",
    "purpose",
    "phenomenon",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a lightweight example_catalog.json from ALIENTEK-style examples.")
    parser.add_argument("--materials-root", default="", help="外部 materials 根目录；也可通过环境变量 STM32F407_MATERIALS_ROOT 指定")
    parser.add_argument("--root-dir", default="", help="Example root directory to scan. Default: <materials-root>/examples")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output example_catalog.json path.")
    return parser.parse_args()


def resolve_root_dir(args: argparse.Namespace) -> Path:
    materials_root = Path(args.materials_root).resolve() if args.materials_root else DEFAULT_MATERIALS_ROOT.resolve()
    if args.root_dir:
        return Path(args.root_dir).resolve()
    return materials_root / "examples"


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("gbk", "gb2312", "utf-8", "utf-8-sig"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    try:
        return path.read_text(encoding="gbk", errors="ignore")
    except OSError:
        return ""


def collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def sanitize_readme_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^/\*+", "", line)
    line = re.sub(r"\*/$", "", line)
    line = re.sub(r"^\*+\s*", "", line)
    return collapse_whitespace(line)


def is_noise_line(line: str) -> bool:
    stripped = collapse_whitespace(line)
    if not stripped or stripped in IGNORE_EXACT_LINES:
        return True
    if stripped.startswith(IGNORE_PREFIXES):
        return True

    compact = re.sub(r"\s+", "", stripped).lower()
    if any(token in compact for token in IGNORE_SUBSTRINGS_COMPACT):
        return True

    return any(pattern.search(stripped) for pattern in IGNORE_LINE_PATTERNS)


def truncate_text(text: str, limit: int) -> str:
    text = collapse_whitespace(text)
    if len(text) <= limit:
        return text
    clipped = text[:limit].rstrip()
    return clipped.rstrip("\uFF0C\u3002\uFF1B\u3001,:; ") + "..."


def detect_section_header(line: str) -> str | None:
    normalized = collapse_whitespace(line)
    if normalized in NON_TARGET_HEADERS:
        return "break"
    for label in NON_TARGET_HEADERS:
        for separator in ("\uFF1A", ":"):
            if normalized.startswith(f"{label}{separator}"):
                return "break"
    for separator in ("\uFF1A", ":"):
        if separator in normalized:
            prefix = collapse_whitespace(normalized.split(separator, 1)[0])
            if prefix and prefix not in SECTION_ALIASES and len(prefix) <= 12:
                return "break"
    if normalized in SECTION_ALIASES:
        return SECTION_ALIASES[normalized]

    for label, section in SECTION_ALIASES.items():
        for separator in ("\uFF1A", ":"):
            prefix = f"{label}{separator}"
            if normalized.startswith(prefix):
                return section
    return None


def extract_section_value(line: str, section: str) -> str:
    normalized = collapse_whitespace(line)
    labels = [label for label, value in SECTION_ALIASES.items() if value == section]
    for label in labels:
        for separator in ("\uFF1A", ":"):
            prefix = f"{label}{separator}"
            if normalized.startswith(prefix):
                return collapse_whitespace(normalized[len(prefix) :])
    return ""


def extract_readme_description(path: Path) -> tuple[str, str]:
    raw_text = read_text_with_fallback(path)
    if not raw_text:
        return "", ""

    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    current_section: str | None = None

    for raw_line in raw_text.splitlines():
        line = sanitize_readme_line(raw_line)
        if not line or is_noise_line(line):
            continue

        section = detect_section_header(line)
        if section == "break":
            current_section = None
            continue
        if section is not None:
            current_section = section
            inline_value = extract_section_value(line, section)
            if inline_value and not is_noise_line(inline_value):
                sections[section].append(inline_value)
            continue

        if current_section is None:
            continue
        if len(sections[current_section]) >= 2:
            continue
        sections[current_section].append(line)

    lines: list[str] = []
    for section in SECTION_ORDER:
        lines.extend(sections[section])

    if not lines:
        return "", ""

    description = truncate_text(" ".join(lines), MAX_DESCRIPTION_CHARS)
    summary_source = sections["title"][0] if sections["title"] else lines[0]
    summary = truncate_text(summary_source, MAX_SUMMARY_CHARS)
    if len(summary) < min(24, len(description)):
        summary = truncate_text(description, MAX_SUMMARY_CHARS)
    return summary, description


def normalize_id_from_path(path: str) -> str:
    ascii_seed = path.encode("ascii", errors="ignore").decode("ascii").lower()
    ascii_seed = re.sub(r"[^a-z0-9]+", "_", ascii_seed).strip("_")
    base = f"example_{ascii_seed}" if ascii_seed else "example"
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}"


def iter_user_headers_and_sources(user_dir: Path) -> Iterable[Path]:
    for path in sorted(user_dir.rglob("*.c")):
        yield path
    for path in sorted(user_dir.rglob("*.h")):
        yield path


def build_core_files(example_dir: Path, root_dir: Path) -> list[str]:
    core_files: list[Path] = []

    for candidate in README_CANDIDATES:
        readme_path = example_dir / candidate
        if readme_path.exists():
            core_files.append(readme_path)
            break

    core_files.extend(sorted(example_dir.glob("*.ioc")))

    user_dir = example_dir / "User"
    if user_dir.exists():
        core_files.extend(iter_user_headers_and_sources(user_dir))

    return [str(path.relative_to(root_dir)).replace("\\", "/") for path in core_files]


def infer_categories(example_dir: Path, root_dir: Path, text_blob: str = "") -> list[str]:
    categories: list[str] = []
    rel_parts = [part.strip().lower() for part in example_dir.relative_to(root_dir).parts]
    joined = " ".join(rel_parts)
    signal_text = f"{joined} {text_blob.lower()}".strip()

    for token in ("hal", "sensors", "display", "communication"):
        if token in rel_parts and token not in categories:
            categories.append(token)

    category_keywords = {
        "gpio": ("led", "跑马灯", "gpio", "蜂鸣器", "按键"),
        "exti": ("exti", "外部中断"),
        "usart": ("串口", "uart", "usart"),
        "tim": ("定时器", "timer", "tim"),
        "pwm": ("pwm",),
        "input_capture": ("输入捕获", "capture"),
        "encoder": ("编码器", "脉冲计数", "测速"),
        "dma": ("dma",),
        "adc": ("adc", "采集", "模数转换", "模拟量"),
        "dac": ("dac",),
        "iic": ("iic", "i2c"),
        "spi": ("spi",),
        "can": ("can",),
        "oled": ("oled",),
        "tft": ("tft", "tftlcd", "fsmc", "mcu屏"),
        "touch": ("touch", "tp", "触摸", "电阻式触摸", "电容式触摸"),
        "audio": ("audio", "music", "wav", "i2s", "iis", "es8388"),
        "fsmc": ("fsmc", "8080并口", "并口驱动"),
        "sram": ("sram", "外部sram"),
        "sensor": ("传感器", "ds18b20", "dht11", "磁力计", "三轴"),
    }

    for category, keywords in category_keywords.items():
        if any(keyword in signal_text for keyword in keywords) and category not in categories:
            categories.append(category)

    return categories


def derive_keywords(title: str, path: str, summary: str, description: str) -> list[str]:
    pool = " ".join([title, path, summary, description]).lower()
    ascii_tokens = re.findall(r"[a-z][a-z0-9_]{1,}", pool)
    cjk_phrases = re.findall(r"[\u4e00-\u9fff]{2,12}", pool)

    ordered: list[str] = []
    for token in ascii_tokens + cjk_phrases:
        cleaned = token.strip("_").lower()
        if not cleaned or cleaned in STOPWORDS:
            continue
        if cleaned not in ordered:
            ordered.append(cleaned)

    return ordered[:MAX_KEYWORDS]


def is_example_node(path: Path) -> bool:
    has_readme = any((path / name).is_file() for name in README_CANDIDATES)
    has_user_dir = (path / "User").is_dir()
    return has_readme and has_user_dir


def collect_example_nodes(root_dir: Path) -> list[Path]:
    return [path for path in sorted(root_dir.rglob("*")) if path.is_dir() and is_example_node(path)]


def build_entry(example_dir: Path, root_dir: Path) -> dict:
    relative_path = str(example_dir.relative_to(root_dir)).replace("\\", "/")
    readme_path = next((example_dir / name for name in README_CANDIDATES if (example_dir / name).exists()), example_dir / "readme.txt")
    summary, description = extract_readme_description(readme_path)
    core_files = build_core_files(example_dir, root_dir)
    keywords = derive_keywords(
        title=example_dir.name,
        path=relative_path,
        summary=summary,
        description=description,
    )
    categories = infer_categories(example_dir, root_dir, text_blob=f"{summary} {description}")

    return {
        "id": normalize_id_from_path(relative_path),
        "title": example_dir.name,
        "path": relative_path,
        "category": categories,
        "summary": summary,
        "description": description,
        "keywords": keywords,
        "core_files_to_read": core_files,
        "has_ioc": any(item.lower().endswith(".ioc") for item in core_files),
        "has_user_dir": True,
    }


def generate_catalog(root_dir: Path) -> list[dict]:
    if not root_dir.exists():
        raise FileNotFoundError(f"Root directory not found: {root_dir}")

    entries = [build_entry(example_dir, root_dir) for example_dir in collect_example_nodes(root_dir)]
    entries.sort(key=lambda item: str(item["path"]))
    return entries


def main() -> int:
    args = parse_args()
    root_dir = resolve_root_dir(args)
    output_path = Path(args.output).resolve()

    entries = generate_catalog(root_dir)
    output_path.write_text(json.dumps(entries, ensure_ascii=False, indent=4), encoding="utf-8")
    print(f"Generated {len(entries)} entries -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
