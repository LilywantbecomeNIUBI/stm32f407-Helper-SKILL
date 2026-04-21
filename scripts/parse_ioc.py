#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
DEFAULT_SEARCH_ROOT = REPO_ROOT

PIN_NAME_RE = re.compile(r"^(P[A-Z]\d+|PH\d+|PC\d+-OSC\d+_.*|PH\d+-OSC_.*|PA\d+|PB\d+|PF\d+|PG\d+|PI\d+|VP_.*)$")
SYSTEM_IRQS = {
    "BusFault_IRQn",
    "DebugMonitor_IRQn",
    "HardFault_IRQn",
    "MemoryManagement_IRQn",
    "NonMaskableInt_IRQn",
    "PendSV_IRQn",
    "SVCall_IRQn",
    "SysTick_IRQn",
    "UsageFault_IRQn",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lightweight parser for STM32CubeMX .ioc files.")
    parser.add_argument("ioc", nargs="?", default="", help="Path to a .ioc file. If omitted, auto-search under --search-root.")
    parser.add_argument("--search-root", default=str(DEFAULT_SEARCH_ROOT), help="Search root when .ioc path is omitted.")
    parser.add_argument("--format", dest="output_format", choices=["json", "text"], default="json", help="Output format.")
    return parser.parse_args()


def find_ioc_file(explicit_path: str, search_root: Path) -> Path:
    if explicit_path:
        path = Path(explicit_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f".ioc not found: {path}")
        return path

    candidates = sorted(search_root.rglob("*.ioc"))
    if not candidates:
        raise FileNotFoundError(f"No .ioc found under: {search_root}")
    return candidates[0]


def parse_bool_like(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def split_key_value(line: str) -> tuple[str, str] | None:
    if "=" not in line or line.startswith("#"):
        return None
    key, value = line.split("=", 1)
    return key.strip(), value.strip()


def pin_sort_key(pin_name: str) -> tuple[int, str]:
    if pin_name.startswith("VP_"):
        return (1, pin_name)
    return (0, pin_name)


def parse_ioc(path: Path) -> Dict[str, Any]:
    raw_lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    entries: Dict[str, str] = {}
    for raw_line in raw_lines:
        pair = split_key_value(raw_line)
        if pair is None:
            continue
        key, value = pair
        entries[key] = value

    ips = [entries.get(f"Mcu.IP{i}", "") for i in range(int(entries.get("Mcu.IPNb", "0") or "0"))]
    ips = [ip for ip in ips if ip]
    pins = [entries.get(f"Mcu.Pin{i}", "") for i in range(int(entries.get("Mcu.PinsNb", "0") or "0"))]
    pins = [pin for pin in pins if pin]

    pin_details: List[Dict[str, Any]] = []
    for pin in sorted(pins, key=pin_sort_key):
        info: Dict[str, Any] = {
            "name": pin,
            "signal": entries.get(f"{pin}.Signal", ""),
            "mode": entries.get(f"{pin}.Mode", ""),
        }
        label = entries.get(f"{pin}.GPIO_Label", "")
        if label:
            info["label"] = label
        params = entries.get(f"{pin}.GPIOParameters", "")
        if params:
            info["gpio_parameters"] = [part.strip() for part in params.split(",") if part.strip()]
        for suffix in ("GPIO_Speed", "PinState", "Locked", "Pull", "GPIO_PuPd", "GPIO_ModeDefaultOutputPP"):
            value = entries.get(f"{pin}.{suffix}", "")
            if value:
                info[suffix] = value
        pin_details.append(info)

    enabled_interrupts: List[Dict[str, Any]] = []
    for key, value in entries.items():
        if not key.startswith("NVIC.") or not key.endswith("_IRQn"):
            continue
        irq_name = key.split(".", 1)[1]
        parts = value.split("\\:")
        enabled = parse_bool_like(parts[0]) if parts else None
        if enabled:
            item: Dict[str, Any] = {"irq": irq_name, "raw": value}
            if len(parts) > 2 and parts[1].isdigit() and parts[2].isdigit():
                item["preempt_priority"] = int(parts[1])
                item["sub_priority"] = int(parts[2])
            enabled_interrupts.append(item)

    app_irqs = [item for item in enabled_interrupts if item["irq"] not in SYSTEM_IRQS]

    dma_related: List[Dict[str, str]] = []
    for key, value in entries.items():
        key_lower = key.lower()
        if key.startswith("DMA.") or ".dma" in key_lower:
            dma_related.append({"key": key, "value": value})

    peripheral_config: Dict[str, Dict[str, str]] = {}
    for key, value in entries.items():
        prefix = key.split(".", 1)[0]
        if prefix in {"ProjectManager", "Mcu", "RCC", "NVIC", "PinOutPanel", "KeepUserPlacement", "GPIO", "MxCube", "MxDb", "File", "board"}:
            continue
        if prefix.startswith("VP_"):
            continue
        if PIN_NAME_RE.match(prefix):
            continue
        peripheral_config.setdefault(prefix, {})[key.split(".", 1)[1] if "." in key else key] = value

    clock_summary = {
        "sysclk_source": entries.get("RCC.SYSCLKSource", ""),
        "sysclk_hz": entries.get("RCC.SYSCLKFreq_VALUE", ""),
        "hclk_hz": entries.get("RCC.HCLKFreq_Value", ""),
        "apb1_hz": entries.get("RCC.APB1Freq_Value", ""),
        "apb2_hz": entries.get("RCC.APB2Freq_Value", ""),
        "pll_source": entries.get("RCC.PLLSourceVirtual", ""),
        "pll_m": entries.get("RCC.PLLM", ""),
        "pll_n": entries.get("RCC.PLLN", ""),
        "pll_q": entries.get("RCC.PLLQ", ""),
        "hse_hz": entries.get("RCC.HSE_VALUE", ""),
        "hsi_hz": entries.get("RCC.HSI_VALUE", ""),
        "lsi_hz": entries.get("RCC.LSI_VALUE", ""),
    }

    project_summary = {
        "project_name": entries.get("ProjectManager.ProjectName", ""),
        "project_file": entries.get("ProjectManager.ProjectFileName", ""),
        "toolchain": entries.get("ProjectManager.TargetToolchain", ""),
        "main_location": entries.get("ProjectManager.MainLocation", ""),
        "firmware_package": entries.get("ProjectManager.FirmwarePackage", ""),
    }

    return {
        "ioc_path": str(path),
        "project": project_summary,
        "mcu": {
            "family": entries.get("Mcu.Family", ""),
            "name": entries.get("Mcu.Name", ""),
            "user_name": entries.get("Mcu.UserName", ""),
            "package": entries.get("Mcu.Package", ""),
        },
        "enabled_ips": ips,
        "pins": pin_details,
        "clock": clock_summary,
        "nvic": {
            "priority_group": entries.get("NVIC.PriorityGroup", ""),
            "enabled_irqs": enabled_interrupts,
            "application_irqs": app_irqs,
            "force_enable_dma_vector": parse_bool_like(entries.get("NVIC.ForceEnableDMAVector", "")),
        },
        "dma": dma_related,
        "peripherals": peripheral_config,
        "raw_stats": {
            "total_pins": len(pin_details),
            "enabled_ip_count": len(ips),
            "enabled_irq_count": len(enabled_interrupts),
            "application_irq_count": len(app_irqs),
            "dma_entry_count": len(dma_related),
        },
    }


def format_text(result: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"ioc: {result['ioc_path']}")
    project = result["project"]
    lines.append(f"project: {project.get('project_name', '')}")
    lines.append(f"mcu: {result['mcu'].get('name', '')} / {result['mcu'].get('package', '')}")
    lines.append("")

    lines.append("enabled_ips:")
    for ip in result.get("enabled_ips", []):
        lines.append(f"- {ip}")
    lines.append("")

    lines.append("clock:")
    for key, value in result.get("clock", {}).items():
        if value:
            lines.append(f"- {key}: {value}")
    lines.append("")

    lines.append("application_irqs:")
    for irq in result.get("nvic", {}).get("application_irqs", []):
        label = irq["irq"]
        if "preempt_priority" in irq:
            label += f" (preempt={irq['preempt_priority']}, sub={irq['sub_priority']})"
        lines.append(f"- {label}")
    lines.append("")

    lines.append("pins:")
    for pin in result.get("pins", [])[:20]:
        parts = [pin["name"]]
        if pin.get("label"):
            parts.append(f"label={pin['label']}")
        if pin.get("signal"):
            parts.append(f"signal={pin['signal']}")
        if pin.get("mode"):
            parts.append(f"mode={pin['mode']}")
        lines.append(f"- {'; '.join(parts)}")
    if len(result.get("pins", [])) > 20:
        lines.append(f"- ... ({len(result['pins']) - 20} more)")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    ioc_path = find_ioc_file(args.ioc, Path(args.search_root).resolve())
    result = parse_ioc(ioc_path)
    if args.output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
