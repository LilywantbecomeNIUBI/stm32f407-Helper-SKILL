#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
search_materials.py

第一版目标：
1. 根据自然语言任务识别模块。
2. 优先从例程目录索引中定位推荐例程。
3. 再从教材目录索引中定位推荐章节。
4. 汇总 CubeMX 配置建议、引脚提醒和建议文件落点。

当前版本是“目录级检索”，不是源码级或 PDF 全文级检索。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Set, Tuple

try:
    from parse_ioc import parse_ioc
    from scan_current_project import scan_project
except Exception:
    parse_ioc = None
    scan_project = None


SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"
DEFAULT_MATERIALS_ROOT = Path(os.environ.get("STM32F407_MATERIALS_ROOT", SCRIPT_DIR.parent / "materials"))

DEFAULT_EXAMPLE_CATALOG = ASSETS_DIR / "example_catalog.json"
DEFAULT_BOOK_CATALOG = ASSETS_DIR / "book_catalog.json"
DEFAULT_BOOK_EXCERPT_CATALOG = ASSETS_DIR / "book_excerpt_catalog.json"
DEFAULT_PIN_CATALOG = ASSETS_DIR / "pin_catalog.json"
DEFAULT_EXAMPLES_ROOT = DEFAULT_MATERIALS_ROOT / "examples"
DEFAULT_EXAMPLE_TREE_RULES = ASSETS_DIR / "example_tree_rules.json"
DEFAULT_PROJECT_ROOT = SCRIPT_DIR.parent

MIN_SCORE = 5
MIN_EXAMPLE_FILE_SCORE = 6


MODULE_KEYWORDS: Dict[str, List[str]] = {
    "cubemx": ["cubemx", "stm32cubemx", "ioc", "新建工程", "代码生成", "project manager"],
    "clock": ["clock", "sysclk", "pll", "apb", "主频", "时钟", "时钟树", "波特率", "采样率"],
    "gpio": ["gpio", "gpio输出", "led", "跑马灯"],
    "key": ["key", "button", "按键", "按键扫描", "按键输入"],
    "beep": ["beep", "buzzer", "蜂鸣器"],
    "exti": ["exti", "external interrupt", "外部中断", "按键中断"],
    "usart": ["uart", "usart", "serial", "串口", "串口通信", "串口接收", "串口发送", "空闲中断"],
    "tim": ["tim", "timer", "定时器", "定时"],
    "pwm": ["pwm", "占空比", "pwm输出"],
    "input_capture": ["input capture", "capture", "输入捕获", "脉宽测量", "频率测量"],
    "encoder": ["encoder", "编码器", "测速"],
    "adc": ["adc", "采样", "电压采集", "模数转换", "模拟量"],
    "dma": ["dma", "连续搬运", "环形缓冲", "dma接收", "dma读取"],
    "iic": ["iic", "i2c", "eeprom", "scl", "sda"],
    "spi": ["spi", "flash", "sck", "miso", "mosi"],
    "oled": ["oled", "ssd1306", "oled显示", "oled屏", "字符显示"],
    "tft": ["tft", "lcd", "tftlcd", "fsmc", "mcu屏", "mcu screen", "tft显示", "液晶"],
    "touch": ["touch", "tp", "触摸", "触摸屏", "触摸坐标", "校准"],
    "audio": ["audio", "music", "wav", "i2s", "iis", "es8388", "音频", "音乐", "播放器"],
    "sensor": ["sensor", "传感器", "ds18b20", "dht11", "mpu", "nrf24l01", "磁力计"],
}

IMPLIED_MODULES: Dict[str, List[str]] = {
    "pwm": ["tim"],
    "input_capture": ["tim"],
    "encoder": ["tim"],
    "audio": ["dma"],
}


CUBEMX_TOPIC_RULES: Dict[str, List[str]] = {
    "gpio_input": [
        "配置目标 GPIO 为 Input 模式",
        "确认 Pull-up / Pull-down / No pull 设置",
        "确认引脚未与板载资源冲突",
    ],
    "gpio_output": [
        "配置目标 GPIO 为 Output 模式",
        "确认输出初始电平",
        "确认引脚未与板载资源冲突",
    ],
    "gpio_exti": [
        "配置目标 GPIO 为 External Interrupt 模式",
        "选择触发边沿（Rising / Falling / Both）",
        "开启对应 EXTI NVIC 中断",
        "确认引脚未与板载资源冲突",
    ],
    "uart_enable": [
        "启用目标 USART/UART 实例",
        "选择 Asynchronous 模式",
        "确认波特率配置",
    ],
    "uart_gpio_af": [
        "确认 TX/RX GPIO 与 AF 配置",
        "确认对应引脚未与板载资源冲突",
    ],
    "uart_nvic": [
        "若使用中断接收，开启 USART 全局中断",
        "确认 NVIC 优先级设置",
    ],
    "uart_dma": [
        "若使用 DMA，配置 USART RX/TX 对应 DMA",
        "确认 Normal / Circular 模式是否符合需求",
    ],
    "tim_base": [
        "选择目标 TIM 实例",
        "配置 Prescaler / Period",
        "若使用中断，开启对应 TIM NVIC",
    ],
    "tim_pwm": [
        "选择目标 TIM 实例和 PWM Channel",
        "配置 PWM Generation 模式",
        "配置 Prescaler / Period",
        "确认 GPIO AF 与输出引脚",
    ],
    "tim_input_capture": [
        "选择目标 TIM 实例和 Input Capture Channel",
        "确认 GPIO AF 与输入引脚",
        "配置极性、预分频、滤波等参数",
        "若需要中断，开启 TIM NVIC",
    ],
    "tim_encoder": [
        "选择 Encoder 模式",
        "确认 A/B 相输入引脚与 AF",
        "配置计数模式和滤波参数",
    ],
    "tim_nvic": [
        "开启对应 TIM 中断",
        "确认 NVIC 优先级设置",
    ],
    "adc_enable": [
        "启用目标 ADC 实例",
        "确认 ADC 时钟来源与分频",
    ],
    "adc_channel": [
        "配置 ADC 通道与 Rank",
        "确认 Sampling Time",
        "确认引脚为 Analog 模式",
    ],
    "adc_dma": [
        "为 ADC 配置 DMA",
        "确认 DMA continuous requests",
        "确认 DMA 模式（Normal / Circular）",
    ],
    "adc_trigger": [
        "确认单次 / 连续 / 外部触发方式",
        "若使用定时触发，确认触发源配置",
    ],
    "dma_basic": [
        "确认 DMA Stream / Channel / Request 绑定",
        "确认方向、数据宽度、优先级",
        "确认 Normal / Circular 模式",
    ],
    "i2c_enable": [
        "启用目标 I2C 实例",
        "确认时钟速率配置",
    ],
    "i2c_gpio_af": [
        "确认 SCL/SDA GPIO 与 AF 配置",
        "确认上拉设置或外部上拉条件",
        "确认引脚未与板载资源冲突",
    ],
    "spi_enable": [
        "启用目标 SPI 实例",
        "确认 Master / Slave 模式",
        "确认数据位宽、CPOL、CPHA、NSS 管理方式",
    ],
    "spi_gpio_af": [
        "确认 SCK/MISO/MOSI GPIO 与 AF 配置",
        "确认片选脚方案",
        "确认引脚未与板载资源冲突",
    ],
    "oled_bus": [
        "确认 OLED 使用的底层总线（I2C 或 SPI）",
        "确认底层总线外设已在 CubeMX 中配置",
        "确认 OLED 控制脚或地址配置",
    ],
    "tft_bus": [
        "确认 TFT 使用的总线类型是 FSMC/FMC、SPI 还是普通 GPIO 并口方案",
        "确认显示相关 GPIO、总线外设和背光/复位控制脚都已在 CubeMX 中占好资源",
        "如果后续还要接触摸或外部 SRAM，先一起检查显示总线是否会与它们冲突",
    ],
    "touch_bus": [
        "确认触摸接口类型是电阻触摸还是电容触摸，以及对应控制器方案",
        "确认触摸链路依赖的 GPIO、SPI、I2C、ADC 中哪些外设需要先在 CubeMX 中启用",
        "确认触摸中断脚、复位脚、校准流程与屏幕总线没有资源冲突",
    ],
    "tft_mcu_panel": [
        "如果是 MCU 屏或 8080 并口 TFTLCD，先确认是否使用 FSMC/FMC 硬件总线，而不是普通 GPIO 模拟",
        "确认 LCD 的 CS、RS(DC)、WR、RD、RST、BL 等控制脚已经分配且不冲突",
        "确认 D0-D15 等数据线与板卡连线和 FSMC/FMC AF 映射一致",
    ],
    "touch_panel_flow": [
        "电阻触摸要额外确认 ADC 与 GPIO 的切换关系、采样方向和校准流程是否在软件里处理完整",
        "电容触摸要确认 I2C/SPI 控制链路、中断脚/RESET 脚以及触摸点上报流程已经打通",
        "如果触摸屏与显示屏共享底层总线，先确认显示初始化时序不会影响触摸初始化",
    ],
    "fsmc_bus": [
        "启用 FSMC/FMC 后，确认 NE、NOE、NWE、Axx、Dxx 等引脚都已配置为正确 AF",
        "确认 FSMC/FMC 的 Bank、数据宽度和读写时序与目标 LCD/SRAM 手册一致",
        "如果项目同时挂接 LCD 和 SRAM，确认各自使用的 Bank 或 CS 线没有冲突",
    ],
    "sram_bus": [
        "外部 SRAM 任务需要确认 FSMC/FMC 已启用，并且时序参数匹配目标器件",
        "确认 SRAM 的地址线、数据线、CS/OE/WE 等控制线没有被 LCD 或其他外设复用",
        "如果外部 SRAM 用作字库、图片或显示缓冲区，还要一起检查 FATFS/SD 到内存的数据路径",
    ],
    "audio_bus": [
        "确认音频播放链路使用的音频总线（I2S / IIS / SAI）以及编解码器控制总线",
        "确认音频数据 DMA、采样率、主时钟/位时钟/左右声道时钟配置",
        "确认喇叭/耳机输出、电源放大器使能脚和 SD/FATFS 文件源链路",
    ],
    "sensor_bus": [
        "确认传感器依赖的底层总线（GPIO / ADC / I2C / SPI / TIM / EXTI）",
        "确认中断脚、采样脚、总线脚已在 CubeMX 中配置",
    ],
}

MODULE_FILE_SUGGESTIONS: Dict[str, List[str]] = {
    "cubemx": ["*.ioc", "Core/Src/main.c", "Core/Inc/main.h"],
    "clock": ["*.ioc", "Core/Src/system_stm32f4xx.c", "Core/Src/main.c"],
    "gpio": ["Core/Inc/bsp_gpio.h", "Core/Src/bsp_gpio.c"],
    "key": ["Core/Inc/bsp_key.h", "Core/Src/bsp_key.c"],
    "beep": ["Core/Inc/bsp_beep.h", "Core/Src/bsp_beep.c"],
    "exti": ["Core/Inc/app_exti.h", "Core/Src/app_exti.c"],
    "usart": ["Core/Inc/app_uart.h", "Core/Src/app_uart.c"],
    "tim": ["Core/Inc/app_tim.h", "Core/Src/app_tim.c"],
    "pwm": ["Core/Inc/app_pwm.h", "Core/Src/app_pwm.c"],
    "input_capture": ["Core/Inc/app_capture.h", "Core/Src/app_capture.c"],
    "encoder": ["Core/Inc/app_encoder.h", "Core/Src/app_encoder.c"],
    "adc": ["Core/Inc/app_adc.h", "Core/Src/app_adc.c"],
    "dma": ["Core/Inc/app_dma_helper.h", "Core/Src/app_dma_helper.c"],
    "iic": ["Core/Inc/bsp_i2c_dev.h", "Core/Src/bsp_i2c_dev.c"],
    "spi": ["Core/Inc/bsp_spi_dev.h", "Core/Src/bsp_spi_dev.c"],
    "oled": ["Core/Inc/bsp_oled.h", "Core/Src/bsp_oled.c", "Core/Src/app_display.c"],
    "tft": ["Core/Inc/bsp_tft.h", "Core/Src/bsp_tft.c", "Core/Src/app_display.c"],
    "touch": ["Core/Inc/bsp_touch.h", "Core/Src/bsp_touch.c", "Core/Src/app_touch.c"],
    "audio": ["Core/Inc/app_audio.h", "Core/Src/app_audio.c", "Core/Src/app_player.c"],
    "fsmc": ["Core/Src/fsmc.c", "Core/Inc/fsmc.h", "*.ioc"],
    "sram": ["Core/Inc/bsp_sram.h", "Core/Src/bsp_sram.c", "Core/Src/fsmc.c"],
    "sensor": ["Core/Inc/bsp_sensor.h", "Core/Src/bsp_sensor.c"],
}


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def load_json_file(path: Path, required: bool = True) -> Any:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"缺少必需文件: {path}")
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败: {path}\n{exc}") from exc


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[_/,+\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def tokenize_ascii(text: str) -> Set[str]:
    return set(re.findall(r"[a-z0-9]+", normalize_text(text)))


def has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def keyword_matches(query_norm: str, query_tokens: Set[str], keyword: str) -> bool:
    kw_norm = normalize_text(keyword)
    if not kw_norm:
        return False

    if has_cjk(kw_norm):
        return kw_norm in query_norm

    kw_tokens = re.findall(r"[a-z0-9]+", kw_norm)
    if not kw_tokens:
        return kw_norm in query_norm

    if len(kw_tokens) == 1:
        return kw_tokens[0] in query_tokens

    return kw_norm in query_norm


def unique_keep_order(items: Iterable[str]) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


GENERIC_QUERY_FRAGMENTS = {
    "实验",
    "例程",
    "模块",
    "显示",
    "功能",
    "方案",
    "使用",
    "测试",
}


def extract_query_fragments(query: str) -> List[str]:
    query_norm = normalize_text(query)
    fragments: List[str] = []

    for part in re.split(r"\s+", query_norm):
        part = part.strip()
        if not part or part in GENERIC_QUERY_FRAGMENTS:
            continue
        if has_cjk(part) or len(part) >= 3:
            fragments.append(part)

    return unique_keep_order(fragments)


def safe_get_list(d: Dict[str, Any], key: str) -> List[Any]:
    value = d.get(key, [])
    return value if isinstance(value, list) else []


def safe_get_dict(d: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = d.get(key, {})
    return value if isinstance(value, dict) else {}


def safe_get_bool(d: Dict[str, Any], key: str) -> bool:
    value = d.get(key, False)
    return value if isinstance(value, bool) else False


def detect_modules(query: str, forced_module: str | None = None) -> List[str]:
    query_norm = normalize_text(query)
    query_tokens = tokenize_ascii(query)
    matched: List[str] = []

    if forced_module:
        if forced_module not in MODULE_KEYWORDS:
            raise ValueError(f"未知模块: {forced_module}")
        matched.append(forced_module)

    for module, keywords in MODULE_KEYWORDS.items():
        if any(keyword_matches(query_norm, query_tokens, kw) for kw in keywords):
            matched.append(module)
    if "sram" in query_tokens:
        matched.append("sram")
    if "fsmc" in query_tokens or "mcu screen" in query_norm:
        matched.append("fsmc")

    if ("空闲中断" in query or "idle" in query_tokens) and ("串口" in query or "uart" in query_tokens or "usart" in query_tokens):
        matched.extend(["usart", "dma"])

    if ("adc" in query_tokens or "采样" in query) and "dma" in query_tokens:
        matched.extend(["adc", "dma"])

    if "oled" in query_tokens and ("显示" in query or "字符串" in query):
        matched.append("oled")

    expanded = list(matched)
    for module in matched:
        expanded.extend(IMPLIED_MODULES.get(module, []))

    if not expanded:
        if "显示" in query and "oled" in query_tokens:
            expanded.append("oled")
        elif "采样" in query or "voltage" in query_tokens:
            expanded.append("adc")
        elif "串口" in query or "serial" in query_tokens:
            expanded.append("usart")

    return unique_keep_order(expanded)


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().lower()


def path_has_marker(path_norm: str, marker: str) -> bool:
    marker_norm = normalize_path(marker)
    if not marker_norm:
        return False
    wrapped = f"/{path_norm}/"
    return path_norm == marker_norm or wrapped.find(f"/{marker_norm}/") >= 0 or path_norm.startswith(f"{marker_norm}/")


def load_example_tree_rules(path: Path) -> Dict[str, Any]:
    data = load_json_file(path, required=False)
    return data if isinstance(data, dict) else {}


def should_skip_example_dir(rel_dir: Path, rules: Dict[str, Any]) -> bool:
    rel_norm = normalize_path(rel_dir.as_posix())
    if not rel_norm:
        return False

    ignore_names = {normalize_path(str(x)) for x in safe_get_list(rules, "ignore_dir_names")}
    ignore_markers = [normalize_path(str(x)) for x in safe_get_list(rules, "ignore_path_markers")]

    for part in rel_dir.parts:
        if normalize_path(part) in ignore_names:
            return True

    return any(path_has_marker(rel_norm, marker) for marker in ignore_markers)


def should_skip_example_file(rel_path: Path, rules: Dict[str, Any]) -> bool:
    rel_norm = normalize_path(rel_path.as_posix())
    ignore_suffixes = {str(x).lower() for x in safe_get_list(rules, "ignore_suffixes")}
    if rel_path.suffix.lower() in ignore_suffixes:
        return True

    ignore_markers = [normalize_path(str(x)) for x in safe_get_list(rules, "ignore_path_markers")]
    return any(path_has_marker(rel_norm, marker) for marker in ignore_markers)


def score_example_file_path(query: str, modules: Sequence[str], rel_path: Path, rules: Dict[str, Any]) -> Tuple[int, List[str]]:
    rel_norm = normalize_path(rel_path.as_posix())
    filename = rel_path.name.lower()
    path_tokens = tokenize_ascii(rel_norm)
    query_tokens = tokenize_ascii(query)

    score = 0
    reasons: List[str] = []

    focus_filenames = {str(x).lower() for x in safe_get_list(rules, "focus_filenames")}
    preferred_markers = [normalize_path(str(x)) for x in safe_get_list(rules, "preferred_path_markers")]
    module_path_keywords = {
        str(key).lower(): [str(item) for item in value]
        for key, value in safe_get_dict(rules, "module_path_keywords").items()
        if isinstance(value, list)
    }
    system_focus = {
        str(key).lower(): [normalize_path(str(item)) for item in value]
        for key, value in safe_get_dict(rules, "system_focus_by_module").items()
        if isinstance(value, list)
    }

    if filename.endswith(".ioc"):
        score += 18
        reasons.append("CubeMX project file")

    if filename in focus_filenames:
        score += 8
        reasons.append("core example file")

    matched_markers = [marker for marker in preferred_markers if path_has_marker(rel_norm, marker)]
    if matched_markers:
        score += 4 + min(4, len(matched_markers))
        reasons.append("inside preferred source tree")

    if path_has_marker(rel_norm, "drivers/bsp"):
        score += 6
        reasons.append("BSP module implementation")

    matched_modules: List[str] = []
    for module in modules:
        keywords = module_path_keywords.get(module, [])
        if any(keyword_matches(rel_norm, path_tokens, kw) for kw in keywords):
            score += 4
            matched_modules.append(module)

        focus_paths = system_focus.get(module, [])
        if any(path_has_marker(rel_norm, marker) for marker in focus_paths):
            score += 3
            matched_modules.append(module)

    if matched_modules:
        reasons.append(f"matches module path: {', '.join(unique_keep_order(matched_modules))}")

    for token in query_tokens:
        if token and token in path_tokens:
            score += 1
    if query and any(keyword_matches(rel_norm, path_tokens, kw) for kw in [query]):
        score += 2
        reasons.append("path matches query")

    if filename.startswith("stm32f4xx_hal_") and "conf" not in filename:
        score -= 6
        reasons.append("vendor HAL driver file")

    return score, unique_keep_order(reasons)


def collect_example_file_hits(
    query: str,
    modules: Sequence[str],
    examples_root: Path,
    rules: Dict[str, Any],
    topk: int,
) -> List[Dict[str, Any]]:
    if not examples_root.exists():
        return []

    hits: List[Dict[str, Any]] = []

    for current_root, dirnames, filenames in os.walk(examples_root):
        current_path = Path(current_root)
        rel_dir = current_path.relative_to(examples_root)
        dirnames[:] = [name for name in dirnames if not should_skip_example_dir(rel_dir / name, rules)]

        for filename in filenames:
            rel_path = rel_dir / filename
            if should_skip_example_file(rel_path, rules):
                continue

            score, reasons = score_example_file_path(query, modules, rel_path, rules)
            if score < MIN_EXAMPLE_FILE_SCORE:
                continue

            hits.append(
                {
                    "path": str(rel_path).replace("\\", "/"),
                    "score": score,
                    "reason": reasons,
                }
            )

    hits.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    return hits[:topk]


def infer_item_categories(item: Dict[str, Any]) -> List[str]:
    explicit = [str(x).lower() for x in safe_get_list(item, "category")]
    text_parts = [
        str(item.get("title", "")),
        str(item.get("path", "")),
        str(item.get("summary", "")),
        str(item.get("description", "")),
        " ".join(str(x) for x in safe_get_list(item, "keywords")),
    ]
    query_like = " ".join(part for part in text_parts if part)
    inferred = detect_modules(query_like) if query_like else []
    return unique_keep_order(explicit + inferred)


def score_catalog_item_v2(query: str, modules: Sequence[str], item: Dict[str, Any]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    query_norm = normalize_text(query)
    query_tokens = tokenize_ascii(query)
    query_fragments = extract_query_fragments(query)

    title_like = normalize_text(str(item.get("title") or item.get("chapter") or ""))
    path_like = normalize_text(str(item.get("path", "")))
    summary = normalize_text(str(item.get("summary", "")))
    description = normalize_text(str(item.get("description", "")))
    categories = infer_item_categories(item)
    keywords = [str(x) for x in safe_get_list(item, "keywords")]
    has_ioc = safe_get_bool(item, "has_ioc")
    core_files = [str(x) for x in safe_get_list(item, "core_files_to_read")]

    matched_categories = [module for module in modules if module in categories]
    if matched_categories:
        score += 6 + max(0, len(matched_categories) - 1) * 2
        reasons.append(f"module overlap: {', '.join(matched_categories)}")

    matched_keywords = [kw for kw in keywords if keyword_matches(query_norm, query_tokens, kw)]
    if matched_keywords:
        score += min(6, len(unique_keep_order(matched_keywords)))
        reasons.append("keyword match")

    title_fragment_hits = [frag for frag in query_fragments if frag in title_like]
    if title_fragment_hits:
        score += 4 + min(4, len(title_fragment_hits))
        reasons.append("title fragment match")

    path_fragment_hits = [frag for frag in query_fragments if frag in path_like]
    if path_fragment_hits:
        score += 3 + min(3, len(path_fragment_hits))
        reasons.append("path fragment match")

    if title_like and query_norm and (query_norm in title_like or any(keyword_matches(title_like, tokenize_ascii(title_like), kw) for kw in matched_keywords)):
        score += 4
        reasons.append("title match")

    if path_like and query_norm and (query_norm in path_like or any(keyword_matches(path_like, tokenize_ascii(path_like), kw) for kw in matched_keywords)):
        score += 3
        reasons.append("path match")

    if summary and query_norm and (query_norm in summary or any(keyword_matches(summary, tokenize_ascii(summary), kw) for kw in matched_keywords)):
        score += 3
        reasons.append("summary match")

    if description and query_norm and (query_norm in description or any(keyword_matches(description, tokenize_ascii(description), kw) for kw in matched_keywords)):
        score += 3
        reasons.append("description match")

    if query_tokens:
        title_token_hits = query_tokens.intersection(tokenize_ascii(title_like))
        path_token_hits = query_tokens.intersection(tokenize_ascii(path_like))
        if title_token_hits:
            score += min(4, len(title_token_hits))
            reasons.append("title token match")
        if path_token_hits:
            score += min(3, len(path_token_hits))
            reasons.append("path token match")

    if has_ioc and modules:
        score += 2
        reasons.append("has ioc")

    if core_files:
        score += min(2, len(core_files))
        reasons.append("has curated core files")

    if {"adc", "dma"}.issubset(set(modules)) and {"adc", "dma"}.issubset(set(categories)):
        score += 4
        reasons.append("covers adc + dma")

    if {"usart", "dma"}.issubset(set(modules)) and "usart" in categories:
        score += 4
        reasons.append("covers uart + dma")

    if {"key", "exti"}.intersection(set(modules)) and ("key" in categories or "exti" in categories):
        score += 2
        reasons.append("covers key/exti")

    if "oled" in modules and "oled" in categories:
        score += 2
        reasons.append("covers oled")

    return score, unique_keep_order(reasons)


def score_catalog_item(query: str, modules: Sequence[str], item: Dict[str, Any]) -> Tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []

    query_norm = normalize_text(query)
    query_tokens = tokenize_ascii(query)

    title_like = normalize_text(str(item.get("title") or item.get("chapter") or ""))
    categories = [str(x).lower() for x in safe_get_list(item, "category")]
    keywords = [str(x) for x in safe_get_list(item, "keywords")]
    summary = normalize_text(str(item.get("summary", "")))

    matched_categories = [m for m in modules if m in categories]
    if matched_categories:
        add = 6 + max(0, len(matched_categories) - 1) * 2
        score += add
        reasons.append(f"命中模块分类: {', '.join(matched_categories)}")

    matched_keywords = [kw for kw in keywords if keyword_matches(query_norm, query_tokens, kw)]
    if matched_keywords:
        score += min(6, len(unique_keep_order(matched_keywords)))
        reasons.append("命中关键词")

    title_hits = [kw for kw in matched_keywords if normalize_text(kw) in title_like]
    if title_hits:
        score += min(4, len(unique_keep_order(title_hits)))
        reasons.append("标题/章节与查询直接相关")

    summary_hits = [kw for kw in matched_keywords if normalize_text(kw) in summary]
    if summary_hits:
        score += min(3, len(unique_keep_order(summary_hits)))
        reasons.append("摘要与查询直接相关")

    if {"adc", "dma"}.issubset(set(modules)) and {"adc", "dma"}.issubset(set(categories)):
        score += 4
        reasons.append("覆盖 ADC + DMA 组合场景")

    if {"usart", "dma"}.issubset(set(modules)) and "usart" in categories:
        score += 4
        reasons.append("覆盖串口 + DMA 组合场景")

    if {"key", "exti"}.intersection(set(modules)) and ("key" in categories or "exti" in categories):
        score += 2
        reasons.append("覆盖按键/外部中断场景")

    if "oled" in modules and "oled" in categories:
        score += 2
        reasons.append("覆盖 OLED 场景")

    return score, unique_keep_order(reasons)


def rank_items(query: str, modules: Sequence[str], catalog: List[Dict[str, Any]], topk: int) -> List[Dict[str, Any]]:
    scored: List[Dict[str, Any]] = []

    for item in catalog:
        score, reasons = score_catalog_item_v2(query, modules, item)
        if score < MIN_SCORE:
            continue

        enriched = dict(item)
        enriched["score"] = score
        enriched["reason"] = reasons
        enriched["_module_overlap"] = len(set(modules).intersection(set(infer_item_categories(item))))
        scored.append(enriched)

    if scored:
        max_overlap = max(int(item.get("_module_overlap", 0)) for item in scored)
        if max_overlap > 0:
            overlap_items = [item for item in scored if int(item.get("_module_overlap", 0)) == max_overlap]
            fallback_items = [
                item
                for item in scored
                if int(item.get("_module_overlap", 0)) < max_overlap and int(item.get("score", 0)) >= MIN_SCORE + 4
            ]
            scored = overlap_items + fallback_items

    scored.sort(
        key=lambda x: (
            -int(x.get("score", 0)),
            str(x.get("title") or x.get("chapter") or ""),
        )
    )
    trimmed = scored[:topk]
    for item in trimmed:
        item.pop("_module_overlap", None)
    return trimmed


def rank_book_excerpts(
    query: str,
    modules: Sequence[str],
    excerpt_catalog: List[Dict[str, Any]],
    ranked_books: Sequence[Dict[str, Any]],
    topk: int,
) -> List[Dict[str, Any]]:
    if not excerpt_catalog:
        return []

    preferred_book_ids = {
        str(item.get("id", "")).strip()
        for item in ranked_books
        if str(item.get("id", "")).strip()
    }
    preferred_categories: Set[str] = set()
    for item in ranked_books:
        preferred_categories.update(str(x).lower() for x in safe_get_list(item, "category"))

    scored: List[Dict[str, Any]] = []
    for item in excerpt_catalog:
        score, reasons = score_catalog_item_v2(query, modules, item)
        if score < MIN_SCORE:
            continue

        enriched = dict(item)
        book_id = str(item.get("book_id", "")).strip()
        excerpt_categories = [str(x).lower() for x in safe_get_list(item, "category")]
        if book_id and book_id in preferred_book_ids:
            score += 4
            reasons.append("matched recommended book section")
        elif preferred_categories and any(category in preferred_categories for category in excerpt_categories):
            score += 2
            reasons.append("aligned with recommended book category")

        enriched["score"] = score
        enriched["reason"] = unique_keep_order(reasons)
        scored.append(enriched)

    scored.sort(
        key=lambda x: (
            -int(x.get("score", 0)),
            str(x.get("chapter") or x.get("title") or x.get("id") or ""),
        )
    )
    return scored[:topk]


def collect_cubemx_checklist(example_items: List[Dict[str, Any]], book_items: List[Dict[str, Any]], modules: Sequence[str]) -> List[str]:
    topics: List[str] = []
    for item in example_items + book_items:
        topics.extend(str(x) for x in safe_get_list(item, "cubemx_topics"))

    if not topics:
        module_fallback = {
            "cubemx": [],
            "clock": [],
            "gpio": ["gpio_output"],
            "key": ["gpio_input"],
            "beep": ["gpio_output"],
            "exti": ["gpio_exti"],
            "usart": ["uart_enable", "uart_gpio_af", "uart_nvic"],
            "tim": ["tim_base"],
            "pwm": ["tim_pwm"],
            "input_capture": ["tim_input_capture"],
            "encoder": ["tim_encoder"],
            "adc": ["adc_enable", "adc_channel"],
            "dma": ["dma_basic"],
            "iic": ["i2c_enable", "i2c_gpio_af"],
            "spi": ["spi_enable", "spi_gpio_af"],
            "oled": ["oled_bus"],
            "tft": ["tft_bus", "tft_mcu_panel"],
            "touch": ["touch_bus", "touch_panel_flow", "tft_bus"],
            "audio": ["audio_bus"],
            "fsmc": ["fsmc_bus", "tft_mcu_panel"],
            "sram": ["fsmc_bus", "sram_bus"],
            "sensor": ["sensor_bus"],
        }
        for module in modules:
            topics.extend(module_fallback.get(module, []))

    checklist: List[str] = []
    for topic in unique_keep_order(topics):
        checklist.extend(CUBEMX_TOPIC_RULES.get(topic, []))

    return unique_keep_order(checklist)


def collect_pin_hints(modules: Sequence[str], pin_catalog: List[Dict[str, Any]]) -> List[str]:
    hints: List[str] = []

    for item in pin_catalog:
        categories = [str(x).lower() for x in safe_get_list(item, "category")]
        if any(module in categories for module in modules):
            hints.extend(str(hint) for hint in safe_get_list(item, "hints"))

    if not hints:
        hints.append("确认目标引脚未与板载 LED / KEY / BEEP / 串口 / 显示 / 传感器资源冲突")
        if any(m in modules for m in ["usart", "iic", "spi", "oled", "tft", "touch", "audio"]):
            hints.append("确认相关通信引脚的复用功能（AF）与板载连接方式一致")
        if "adc" in modules:
            hints.append("确认 ADC 引脚已配置为 Analog，且未被数字功能占用")
        if any(m in modules for m in ["tim", "pwm", "input_capture", "encoder"]):
            hints.append("确认 TIM 通道与实际引脚映射一致")
        if "audio" in modules:
            hints.append("确认音频链路的数据总线、控制总线和 DMA 路径都已在工程里启用")

    return unique_keep_order(hints)


def suggest_files(example_items: List[Dict[str, Any]], modules: Sequence[str]) -> List[str]:
    result: List[str] = []
    for item in example_items:
        result.extend(str(x) for x in safe_get_list(item, "suggested_files"))

    if not result:
        for module in modules:
            result.extend(MODULE_FILE_SUGGESTIONS.get(module, []))

    return unique_keep_order(result)


MODULE_TO_IOC_IPS: Dict[str, List[str]] = {
    "gpio": ["gpio"],
    "key": ["gpio"],
    "beep": ["gpio"],
    "exti": ["gpio", "nvic"],
    "usart": ["usart", "uart"],
    "tim": ["tim"],
    "pwm": ["tim"],
    "input_capture": ["tim"],
    "encoder": ["tim"],
    "adc": ["adc"],
    "dma": ["dma"],
    "iic": ["i2c"],
    "spi": ["spi"],
    "oled": ["i2c", "spi", "gpio"],
    "tft": ["spi", "fsmc", "fmc", "gpio"],
    "touch": ["gpio", "exti", "spi", "i2c", "adc"],
    "audio": ["i2s", "iis", "sai", "dma", "i2c", "gpio"],
    "fsmc": ["fsmc", "fmc", "gpio"],
    "sram": ["fsmc", "fmc", "gpio"],
    "sensor": ["adc", "i2c", "spi", "tim", "gpio", "exti"],
}


def normalize_ioc_enabled_tokens(ioc_scan: Dict[str, Any]) -> Set[str]:
    enabled_ips = ioc_scan.get("enabled_ips", [])
    tokens: Set[str] = set()
    if not isinstance(enabled_ips, list):
        return tokens

    for item in enabled_ips:
        text = normalize_text(str(item))
        tokens.update(re.findall(r"[a-z0-9]+", text))

    if safe_get_list(safe_get_dict(ioc_scan, "nvic"), "application_irqs"):
        tokens.add("nvic")
    if safe_get_list(ioc_scan, "dma"):
        tokens.add("dma")
    return tokens


def module_visible_in_project(
    module: str,
    project_scan: Dict[str, Any] | None,
    ioc_scan: Dict[str, Any] | None,
    enabled_tokens: Set[str],
) -> bool:
    if any(token in enabled_tokens for token in MODULE_TO_IOC_IPS.get(module, [])):
        return True

    pins = safe_get_list(ioc_scan or {}, "pins")
    pin_text = " ".join(
        f"{item.get('signal', '')} {item.get('label', '')}"
        for item in pins
        if isinstance(item, dict)
    ).lower()

    symbols = safe_get_dict(project_scan or {}, "symbols")
    mx_inits = [str(item).lower() for item in safe_get_list(symbols, "mx_inits")]
    callbacks = [str(item).lower() for item in safe_get_list(symbols, "callbacks")]

    if module in {"gpio", "key", "beep"}:
        return "gpio_" in pin_text or "mx_gpio_init" in mx_inits
    if module == "exti":
        return "exti" in pin_text or any("exti" in item for item in callbacks)
    if module == "dma":
        return "dma" in enabled_tokens
    return False


def summarize_project_decision(
    modules: Sequence[str],
    project_scan: Dict[str, Any] | None,
    ioc_scan: Dict[str, Any] | None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "write_code_now": True,
        "status": "ready",
        "reasons": [],
        "manual_cubemx_required": [],
        "rules_file": {
            "exists": False,
            "path": "",
            "needs_generation": False,
            "suggested_command": "",
        },
    }

    if not project_scan and not ioc_scan:
        result["write_code_now"] = False
        result["status"] = "no_project_context"
        result["reasons"] = [
            "No current project or .ioc context was scanned.",
            "Scan the target CubeMX project before deciding whether code can be written safely.",
        ]
        result["manual_cubemx_required"] = [
            "Provide a project root or .ioc so the workflow can verify clocks, peripherals, DMA, and NVIC first."
        ]
        return result

    status = safe_get_dict(project_scan or {}, "status")
    if project_scan and not safe_get_bool(status, "is_cubemx_project") and not ioc_scan:
        result["write_code_now"] = False
        result["status"] = "not_cubemx"
        result["reasons"] = [
            "The scanned project does not look like a CubeMX HAL project.",
        ]
        result["manual_cubemx_required"] = [
            "Confirm the target project root or provide the .ioc file explicitly."
        ]
        return result

    project_rules = safe_get_dict(project_scan or {}, "project_rules")
    result["rules_file"] = {
        "exists": bool(project_rules.get("rules_path")),
        "path": str(project_rules.get("rules_path", "")),
        "needs_generation": safe_get_bool(project_rules, "needs_generation"),
        "suggested_command": str(project_rules.get("suggested_command", "")),
    }

    effective_ioc = ioc_scan
    if effective_ioc is None and project_scan:
        project_ioc = project_scan.get("ioc_summary")
        if isinstance(project_ioc, dict):
            effective_ioc = project_ioc

    if effective_ioc is None:
        result["write_code_now"] = False
        result["status"] = "missing_ioc"
        result["reasons"] = [
            "The project was scanned, but no .ioc configuration was available.",
        ]
        result["manual_cubemx_required"] = [
            "Open CubeMX and confirm peripheral, GPIO, DMA, NVIC, and clock configuration before code generation."
        ]
        return result

    enabled_tokens = normalize_ioc_enabled_tokens(effective_ioc)
    missing_requirements: List[str] = []

    for module in modules:
        if not module_visible_in_project(module, project_scan, effective_ioc, enabled_tokens):
            missing_requirements.append(module)

    if missing_requirements:
        result["write_code_now"] = False
        result["status"] = "cubemx_confirmation_needed"
        result["reasons"] = [
            f"The scanned .ioc does not show clear enablement for: {', '.join(unique_keep_order(missing_requirements))}."
        ]
        result["manual_cubemx_required"] = [
            f"Confirm the CubeMX configuration for {module} before writing application code."
            for module in unique_keep_order(missing_requirements)
        ]
        return result

    if project_scan:
        missing_files: List[str] = []
        for key, label in (
            ("has_main_c", "main.c"),
            ("has_it_c", "stm32f4xx_it.c"),
            ("has_hal_msp_c", "stm32f4xx_hal_msp.c"),
            ("has_hal_conf_h", "stm32f4xx_hal_conf.h"),
        ):
            if not safe_get_bool(status, key):
                missing_files.append(label)

        if missing_files:
            result["status"] = "partial_project_context"
            result["reasons"] = [
                f"The project scan is missing expected HAL skeleton files: {', '.join(missing_files)}."
            ]
            result["manual_cubemx_required"] = [
                "Verify the project root and generated HAL skeleton before patching multiple files."
            ]
            return result

    if result["rules_file"]["needs_generation"]:
        result["write_code_now"] = False
        result["status"] = "rules_generation_recommended"
        result["reasons"] = [
            "The project looks like a CubeMX HAL project, but no stm32-cubemx-rules.json file was found.",
            "Generate the rules file first so later edits can distinguish CubeMX-managed files from user-owned files.",
        ]
        result["manual_cubemx_required"] = [
            "Generate stm32-cubemx-rules.json before multi-file code edits."
        ]
        return result

    result["reasons"] = [
        "Project skeleton and .ioc context are available.",
        "Proceed with code changes on top of the scanned HAL project files.",
    ]
    return result


def build_result(
    query: str,
    modules: Sequence[str],
    examples: List[Dict[str, Any]],
    books: List[Dict[str, Any]],
    book_excerpts: List[Dict[str, Any]],
    cubemx_checklist: List[str],
    pin_hints: List[str],
    suggested_files: List[str],
    example_file_hits: List[Dict[str, Any]],
    project_scan: Dict[str, Any] | None,
    ioc_scan: Dict[str, Any] | None,
    project_decision: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "query": query,
        "normalized_modules": list(modules),
        "project_decision": project_decision,
        "project_scan": project_scan,
        "ioc_scan": ioc_scan,
        "recommended_examples": [
            {
                "id": item.get("id"),
                "name": item.get("title"),
                "path": item.get("path"),
                "score": item.get("score"),
                "reason": item.get("reason", []),
                "summary": item.get("summary", ""),
                "description": item.get("description", ""),
                "keywords": safe_get_list(item, "keywords"),
                "core_files_to_read": safe_get_list(item, "core_files_to_read"),
                "has_ioc": safe_get_bool(item, "has_ioc"),
            }
            for item in examples
        ],
        "recommended_book_sections": [
            {
                "id": item.get("id"),
                "chapter": item.get("chapter"),
                "score": item.get("score"),
                "reason": item.get("reason", []),
                "summary": item.get("summary", ""),
            }
            for item in books
        ],
        "recommended_book_excerpts": [
            {
                "id": item.get("id"),
                "book_id": item.get("book_id", ""),
                "chapter": item.get("chapter") or item.get("title", ""),
                "score": item.get("score"),
                "reason": item.get("reason", []),
                "source_pdf": item.get("source_pdf", ""),
                "page_range": item.get("page_range", ""),
                "key_pages": safe_get_list(item, "key_pages"),
                "summary": item.get("summary", ""),
                "excerpt": item.get("excerpt", ""),
            }
            for item in book_excerpts
        ],
        "cubemx_checklist": cubemx_checklist,
        "pin_hints": pin_hints,
        "suggested_files": suggested_files,
        "example_file_hits": example_file_hits,
    }


def format_text(result: Dict[str, Any]) -> str:
    lines: List[str] = []

    lines.append(f"查询: {result['query']}")
    lines.append("")

    project_decision = safe_get_dict(result, "project_decision")
    if project_decision:
        lines.append("项目判断:")
        lines.append(f"- 状态: {project_decision.get('status', '')}")
        lines.append(f"- 是否可直接写代码: {project_decision.get('write_code_now', False)}")
        for item in safe_get_list(project_decision, "reasons"):
            lines.append(f"- {item}")

        manual_items = safe_get_list(project_decision, "manual_cubemx_required")
        if manual_items:
            lines.append("- 需要先人工确认:")
            for item in manual_items:
                lines.append(f"  - {item}")

        rules_file = safe_get_dict(project_decision, "rules_file")
        if rules_file:
            lines.append(f"- 规则文件已存在: {rules_file.get('exists', False)}")
            if rules_file.get("path"):
                lines.append(f"- 规则文件路径: {rules_file.get('path', '')}")
            if rules_file.get("needs_generation"):
                lines.append(f"- 建议先生成规则文件: {rules_file.get('suggested_command', '')}")
        lines.append("")

    lines.append("识别模块:")
    modules = safe_get_list(result, "normalized_modules")
    if modules:
        for module in modules:
            lines.append(f"- {module}")
    else:
        lines.append("- 未识别到明确模块")
    lines.append("")

    lines.append("推荐例程:")
    examples = result.get("recommended_examples", [])
    if examples:
        for index, item in enumerate(examples, 1):
            lines.append(f"{index}. {item.get('name', '')}")
            if item.get("path"):
                lines.append(f"   路径: {item['path']}")
            if item.get("summary"):
                lines.append(f"   摘要: {item['summary']}")
            if item.get("reason"):
                lines.append(f"   原因: {'；'.join(item['reason'])}")
    else:
        lines.append("- 未找到明显匹配的例程")
    lines.append("")

    lines.append("推荐教材章节:")
    books = result.get("recommended_book_sections", [])
    if books:
        for index, item in enumerate(books, 1):
            lines.append(f"{index}. {item.get('chapter', '')}")
            if item.get("summary"):
                lines.append(f"   摘要: {item['summary']}")
            if item.get("reason"):
                lines.append(f"   原因: {'；'.join(item['reason'])}")
    else:
        lines.append("- 未找到明显匹配的教材章节")
    lines.append("")

    lines.append("教材关键页 / 摘录:")
    book_excerpts = result.get("recommended_book_excerpts", [])
    if book_excerpts:
        for index, item in enumerate(book_excerpts, 1):
            lines.append(f"{index}. {item.get('chapter', '')}")
            if item.get("source_pdf"):
                lines.append(f"   PDF: {item['source_pdf']}")
            if item.get("page_range"):
                lines.append(f"   页码: {item['page_range']}")
            if item.get("key_pages"):
                lines.append(f"   关键页: {', '.join(str(x) for x in item['key_pages'])}")
            if item.get("summary"):
                lines.append(f"   摘要: {item['summary']}")
            if item.get("excerpt"):
                lines.append(f"   摘录: {item['excerpt']}")
    else:
        lines.append("- 当前没有命中教材摘录索引")
    lines.append("")

    lines.append("CubeMX 配置建议:")
    cubemx_checklist = safe_get_list(result, "cubemx_checklist")
    if cubemx_checklist:
        for item in cubemx_checklist:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前没有额外的 CubeMX 配置清单")
    lines.append("")

    lines.append("引脚/资源提醒:")
    pin_hints = safe_get_list(result, "pin_hints")
    if pin_hints:
        for item in pin_hints:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前没有额外的引脚或资源提醒")
    lines.append("")

    lines.append("建议文件落点:")
    suggested_files = safe_get_list(result, "suggested_files")
    if suggested_files:
        for item in suggested_files:
            lines.append(f"- {item}")
    else:
        lines.append("- 当前没有建议新增的文件落点")
    lines.append("")

    lines.append("例程高信号文件命中:")
    example_file_hits = result.get("example_file_hits", [])
    if example_file_hits:
        for item in example_file_hits:
            lines.append(f"- {item.get('path', '')}")
            if item.get("reason"):
                lines.append(f"  原因: {'；'.join(item['reason'])}")
    else:
        lines.append("- 当前 examples 根目录下没有命中高信号文件")
    lines.append("")

    return "\n".join(lines)


def search_materials(
    query: str,
    topk: int = 3,
    forced_module: str | None = None,
    example_catalog_path: Path = DEFAULT_EXAMPLE_CATALOG,
    book_catalog_path: Path = DEFAULT_BOOK_CATALOG,
    book_excerpt_catalog_path: Path = DEFAULT_BOOK_EXCERPT_CATALOG,
    pin_catalog_path: Path = DEFAULT_PIN_CATALOG,
    examples_root: Path = DEFAULT_EXAMPLES_ROOT,
    example_tree_rules_path: Path = DEFAULT_EXAMPLE_TREE_RULES,
    project_root: Path | None = None,
    ioc_path: Path | None = None,
) -> Dict[str, Any]:
    example_catalog = load_json_file(example_catalog_path, required=True)
    book_catalog = load_json_file(book_catalog_path, required=True)
    book_excerpt_catalog = load_json_file(book_excerpt_catalog_path, required=False)
    pin_catalog = load_json_file(pin_catalog_path, required=False)
    example_tree_rules = load_example_tree_rules(example_tree_rules_path)

    if not isinstance(example_catalog, list):
        raise ValueError("example_catalog.json 顶层必须是 list")
    if not isinstance(book_catalog, list):
        raise ValueError("book_catalog.json 顶层必须是 list")
    if not isinstance(pin_catalog, list):
        raise ValueError("pin_catalog.json 顶层必须是 list")

    if not isinstance(book_excerpt_catalog, list):
        raise ValueError("book_excerpt_catalog.json must be a list")

    modules = detect_modules(query, forced_module=forced_module)
    ranked_examples = rank_items(query, modules, example_catalog, topk=topk)
    ranked_books = rank_items(query, modules, book_catalog, topk=topk)
    ranked_book_excerpts = rank_book_excerpts(
        query=query,
        modules=modules,
        excerpt_catalog=book_excerpt_catalog,
        ranked_books=ranked_books,
        topk=topk,
    )

    cubemx_checklist = collect_cubemx_checklist(ranked_examples, ranked_books, modules)
    pin_hints = collect_pin_hints(modules, pin_catalog)
    suggested_files = suggest_files(ranked_examples, modules)
    example_file_hits = collect_example_file_hits(
        query=query,
        modules=modules,
        examples_root=examples_root,
        rules=example_tree_rules,
        topk=max(4, topk * 4),
    )
    resolved_project_root = project_root.resolve() if project_root else None
    resolved_ioc_path = ioc_path.resolve() if ioc_path else None

    project_scan: Dict[str, Any] | None = None
    should_scan_project = resolved_project_root is not None or resolved_ioc_path is not None
    if should_scan_project and scan_project is not None:
        scan_root = resolved_project_root or DEFAULT_PROJECT_ROOT
        project_scan = scan_project(scan_root, explicit_ioc=str(resolved_ioc_path or ""))

    ioc_scan: Dict[str, Any] | None = None
    if resolved_ioc_path and parse_ioc is not None:
        ioc_scan = parse_ioc(resolved_ioc_path)
    elif project_scan and isinstance(project_scan.get("ioc_summary"), dict):
        ioc_scan = project_scan.get("ioc_summary")

    project_decision = summarize_project_decision(modules, project_scan, ioc_scan)

    return build_result(
        query=query,
        modules=modules,
        examples=ranked_examples,
        books=ranked_books,
        book_excerpts=ranked_book_excerpts,
        cubemx_checklist=cubemx_checklist,
        pin_hints=pin_hints,
        suggested_files=suggested_files,
        example_file_hits=example_file_hits,
        project_scan=project_scan,
        ioc_scan=ioc_scan,
        project_decision=project_decision,
    )


def resolve_materials_paths(materials_root: Path | None, args: argparse.Namespace) -> Dict[str, Path]:
    root = materials_root.resolve() if materials_root else DEFAULT_MATERIALS_ROOT.resolve()
    example_catalog = Path(args.example_catalog) if args.example_catalog else DEFAULT_EXAMPLE_CATALOG
    book_catalog = Path(args.book_catalog) if args.book_catalog else DEFAULT_BOOK_CATALOG
    book_excerpt_catalog = Path(args.book_excerpt_catalog) if args.book_excerpt_catalog else DEFAULT_BOOK_EXCERPT_CATALOG
    pin_catalog = Path(args.pin_catalog) if args.pin_catalog else DEFAULT_PIN_CATALOG
    examples_root = Path(args.examples_root) if args.examples_root else root / "examples"

    return {
        "materials_root": root,
        "example_catalog": example_catalog,
        "book_catalog": book_catalog,
        "book_excerpt_catalog": book_excerpt_catalog,
        "pin_catalog": pin_catalog,
        "examples_root": examples_root,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search examples, book sections, CubeMX hints, and file placement suggestions for STM32F407 CubeMX HAL projects."
    )
    parser.add_argument("query", nargs="?", default="", help="自然语言任务描述")
    parser.add_argument("--module", dest="module", default=None, help="强制指定模块，例如 usart / adc / oled")
    parser.add_argument("--keywords", dest="keywords", default="", help="额外关键字")
    parser.add_argument("--topk", dest="topk", type=int, default=3, help="返回前几个结果，默认 3")
    parser.add_argument("--format", dest="output_format", choices=["json", "text"], default="json", help="输出格式")
    parser.add_argument("--materials-root", dest="materials_root", default="", help="外部 materials 根目录；也可通过环境变量 STM32F407_MATERIALS_ROOT 指定")
    parser.add_argument("--example-catalog", dest="example_catalog", default="", help="example_catalog.json 路径；默认使用 skill 内 assets")
    parser.add_argument("--book-catalog", dest="book_catalog", default="", help="book_catalog.json 路径；默认使用 skill 内 assets")
    parser.add_argument("--pin-catalog", dest="pin_catalog", default="", help="pin_catalog.json 路径（可不存在）；默认使用 skill 内 assets")
    parser.add_argument("--examples-root", dest="examples_root", default="", help="外部 examples 根目录；默认从 materials-root/examples 推导")
    parser.add_argument("--example-tree-rules", dest="example_tree_rules", default=str(DEFAULT_EXAMPLE_TREE_RULES), help="example_tree_rules.json path")
    parser.add_argument("--book-excerpt-catalog", dest="book_excerpt_catalog", default="", help="book_excerpt_catalog.json path")
    parser.add_argument("--project-root", dest="project_root", default="", help="Optional CubeMX project root to scan before planning code changes.")
    parser.add_argument("--ioc", dest="ioc_path", default="", help="Optional explicit .ioc path for project-state scanning.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    parts = []
    if args.query:
        parts.append(args.query.strip())
    if args.keywords:
        parts.append(args.keywords.strip())

    final_query = " ".join(part for part in parts if part).strip()
    if not final_query:
        eprint("错误: 请提供查询内容。")
        return 2

    resolved_paths = resolve_materials_paths(
        Path(args.materials_root) if args.materials_root else None,
        args,
    )

    try:
        result = search_materials(
            query=final_query,
            topk=max(1, args.topk),
            forced_module=args.module,
            example_catalog_path=resolved_paths["example_catalog"],
            book_catalog_path=resolved_paths["book_catalog"],
            book_excerpt_catalog_path=resolved_paths["book_excerpt_catalog"],
            pin_catalog_path=resolved_paths["pin_catalog"],
            examples_root=resolved_paths["examples_root"],
            example_tree_rules_path=Path(args.example_tree_rules),
            project_root=Path(args.project_root) if args.project_root else None,
            ioc_path=Path(args.ioc_path) if args.ioc_path else None,
        )
    except Exception as exc:
        eprint(f"执行失败: {exc}")
        return 1

    if args.output_format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_text(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


