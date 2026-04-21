---
name: stm32f407-contest-hal
description: Assist STM32F407 contest development for STM32CubeMX-generated HAL projects in VSCode/Codex. Use when Codex needs to inspect or modify an existing `.ioc` project, plan CubeMX clock/GPIO/DMA/NVIC/peripheral configuration, locate the best local example or textbook chapter before coding, migrate local examples or textbook code into `Core/Inc` + `Core/Src`, and implement or debug GPIO, USART, TIM/PWM, ADC/DMA, I2C, SPI, OLED/TFT, touch display flows, audio playback, and common sensor modules.
---

# STM32F407 Contest HAL

面向 STM32F407 电赛开发，默认项目形态为 STM32CubeMX 生成的 HAL 工程，使用 VSCode/Codex 编辑，代码主要落在 `Core/Inc`、`Core/Src`、`main.c` 和 HAL 回调中。

## 当前版本能力边界

当前版本已经实现：

- 基于本地索引定位教材章节、教材关键页摘录、例程入口和建议阅读文件。
- 解析当前 STM32CubeMX HAL 工程，识别 `.ioc`、`MX_XXX_Init()`、句柄、回调和中断入口。
- 轻量解析 `.ioc` 文件，提取已启用 IP、GPIO、时钟、DMA、NVIC 和外设配置摘要。
- 在底层初始化证据不足时，优先输出 CubeMX 手工确认项，而不是直接假设配置正确。
- 给出 HAL 风格的文件落点规划、模块迁移建议和联调顺序。

当前版本还没有实现：

- 教材 PDF 全文检索或自动摘录生成。
- 自动裁剪整棵例程源码树并提取最小迁移补丁。
- 自动把修改安全地 patch 到用户工程。
- 基于真实板卡资源表的精确引脚冲突判定。

不要把这些未完成能力写成已经完成的事实。如果用户请求这些能力，明确说明当前版本仍以“索引定位 + 工程扫描 + 规划落点”为主。

## 外部资料目录

默认使用外部 `materials` 根目录，推荐结构如下：

```text
materials/
├── textbook/
│   ├── Stm32F4开发指南.pdf
│   ├── Stm32F4开发指南.index.json
│   └── ...
├── examples/
│   ├── hal/
│   ├── sensors/
│   ├── display/
│   └── communication/
├── pinout/
│   ├── board-pinout.pdf
│   ├── pin-map.xlsx
│   └── ...
├── board/
│   ├── schematic.pdf
│   ├── board-resources.md
│   └── ...
└── datasheets/
    ├── oled-ssd1306.pdf
    ├── ds18b20.pdf
    └── ...
```

资料根目录优先级如下：

1. `--materials-root`
2. 环境变量 `STM32F407_MATERIALS_ROOT`
3. skill 目录下的 `materials/`

除非用户明确给了其他路径，否则只在这个资料根目录下查资料，不要到处猜测路径。

## 资料与脚本位置

- 教材章节索引：`assets/book_catalog.json`
- 教材关键页摘录索引：`assets/book_excerpt_catalog.json`
- 例程索引：`assets/example_catalog.json`
- 板级资源提醒：`assets/pin_catalog.json`
- 目录级检索脚本：`scripts/search_materials.py`
- 当前工程扫描：`scripts/scan_current_project.py`
- `.ioc` 解析：`scripts/parse_ioc.py`
- 教材摘录索引生成：`scripts/generate_book_excerpt_catalog.py`
- 规则参考：`references/book-index.md`、`references/cubemx-boundary.md`、`references/module-playbook.md`、`references/display-audio-playbook.md`

## 默认假设

- 目标芯片为 STM32F407 系列。
- 当前工程是 STM32CubeMX 生成的 HAL 工程，或至少存在 `.ioc` 和 `MX_XXX_Init()` 证据。
- 项目默认沿用 `Core/Inc + Core/Src` 结构，不默认重构为更复杂的 BSP/APP 多层目录。
- 除非用户明确要求，否则不默认引入 RTOS、不默认切换到 LL、不默认改启动文件和链接脚本。
- 第一版实现优先最小可运行补丁，优先保守、可联调、容易回退。

## 固定流程

1. 先查资料索引，再决定读哪些具体文件。
2. 先扫当前工程和 `.ioc`，再判断是否能安全写代码。
3. 先判断是否卡在 CubeMX 边界，再决定停在配置建议还是继续改代码。
4. 先给文件落点和改动计划，再给代码或补丁。
5. 最后给联调顺序和排错路径。

## 优先调用目录级检索脚本

当任务属于以下任一类型时，先运行目录级检索脚本，而不是直接凭印象回答：

- 用户问“先看哪个例程”“先看教材哪一章”“先看教材哪几页”。
- 用户要做 ADC/DMA、OLED、串口 DMA、按键中断、PWM、输入捕获、I2C、SPI、传感器等高频模块。
- 用户要把本地例程迁移到 CubeMX HAL 工程。
- 用户还没给具体工程代码，只给了功能目标。
- 用户需要先得到 CubeMX 配置建议、引脚提醒、建议文件落点。

推荐调用：

```bash
python scripts/search_materials.py "<用户原始任务>" --materials-root "<materials_root>" --format json
```

模块非常明确时，可以额外指定：

```bash
python scripts/search_materials.py --module usart --keywords "dma idle receive" --materials-root "<materials_root>" --format json
```

读取结果时优先关注：

- `recommended_examples`
- `recommended_book_sections`
- `recommended_book_excerpts`
- `cubemx_checklist`
- `pin_hints`
- `suggested_files`
- `example_file_hits`

先读索引命中结果，再按需打开少量具体资料，不要一开始就展开整个 `materials` 目录树。

如果脚本返回结果很弱、没有明显匹配、或多个方向互相冲突，再回退到 `references/*.md` 和本地 `rg` 搜索补充判断。

## Project-First Automation Flow

当用户已经有本地 STM32CubeMX HAL 工程时，不要只从例程开始，要先扫当前工程，再决定能不能安全写代码。

默认顺序：

1. 扫描当前工程骨架。
2. 解析当前 `.ioc`。
3. 带工程上下文执行资料检索。
4. 决定是停在 CubeMX 配置建议，还是继续输出代码落点和实现补丁。

推荐命令：

```bash
python scripts/scan_current_project.py "<project_root>" --format json
python scripts/parse_ioc.py "<path-to-ioc>" --format json
python scripts/search_materials.py "<task>" --materials-root "<materials_root>" --project-root "<project_root>" --ioc "<path-to-ioc>" --format json
```

解释规则：

- 如果 `project_decision.write_code_now` 是 `false`，不要直接写代码。
- 如果 `project_decision.status` 是 `missing_ioc`、`not_cubemx` 或 `cubemx_confirmation_needed`，先停在 CubeMX 配置建议。
- 用 `project_scan.files`、`project_scan.symbols` 和 `ioc_scan` 判断代码落点、回调入口和已存在的句柄。
- 用 `project_scan.management_by_file`、`project_scan.management_summary` 和 `project_scan.editable_summary` 判断哪些文件由 CubeMX 管理、哪些文件只能改 `USER CODE` 区块、哪些文件适合自由维护。
- 如果 `project_scan.project_rules.needs_generation` 是 `true`，先生成 `stm32-cubemx-rules.json`，再继续多文件代码修改。
- 只有在工程骨架和 `.ioc` 上下文都存在且一致时，才继续做多文件代码修改。

## Generated Files And Editable Zones

不要只靠文件名猜哪些文件能改。先识别文件归属，再决定代码落点。

默认流程：

1. 运行 `scripts/scan_current_project.py`
2. 如果缺少 `stm32-cubemx-rules.json`，先运行 `scripts/generate_cubemx_rules.py`
3. 再读取 `management_by_file`
4. 优先把新逻辑放到 `user_owned` 文件，或新增 `app_*.c/.h`、`bsp_*.c/.h`
5. 如果文件是 `cubemx_generated`，按 `editable_strategy` 决定是否只能改 `USER CODE` 区块
6. 如果文件是 `cubemx_project_manifest`，回到 CubeMX 修改，不要手写伪补丁

当检测到以下条件同时成立时，默认生成第一版规则文件：

- 当前工程存在 `.ioc`
- 工程看起来是 CubeMX HAL 工程
- 工程根目录还没有 `stm32-cubemx-rules.json`

推荐命令：

```bash
python scripts/generate_cubemx_rules.py "<project_root>"
```

规则文件生成后，重新运行：

```bash
python scripts/scan_current_project.py "<project_root>" --format json
```

默认解释规则：

- `cubemx_project_manifest`
  例如 `.ioc`，只能在 CubeMX 里修改。
- `cubemx_generated`
  例如 `main.c`、`gpio.c`、`usart.c`、`stm32f4xx_it.c`，通常只能改 `USER CODE` 区块。
- `user_owned`
  例如 `app_uart.c`、`app_adc.c`、`bsp_oled.c`，适合长期放业务逻辑。
- `vendor_or_framework`
  例如 `Drivers/`、`Middlewares/`，默认避免手工修改。

如果当前工程布局不标准，允许用户在工程根目录放一个项目规则文件：

`stm32-cubemx-rules.json`

格式参考：

- `references/cubemx-file-ownership.md`
- `assets/stm32-cubemx-rules.template.json`

当给出补丁计划时，必须明确说明：

- 哪些文件是 CubeMX 自动生成的
- 哪些文件只能改 `USER CODE BEGIN/END`
- 哪些文件是用户自管文件，适合放新增业务逻辑

## Auto-Generate Rules File

把 `stm32-cubemx-rules.json` 视为新 CubeMX 工程的默认配套文件，而不是可有可无的附件。

当用户第一次把一个新工程交给你时：

1. 先扫描工程
2. 如果缺规则文件，先生成第一版 `stm32-cubemx-rules.json`
3. 再重新扫描工程
4. 再决定代码落点和补丁策略

生成脚本：

```bash
python scripts/generate_cubemx_rules.py "<project_root>"
```

这个脚本的目标不是完美覆盖所有项目习惯，而是尽快建立一份“可解释的初版文件归属声明”，让后续自动修改不再靠猜。

如果规则文件已经存在，不要无条件覆盖。优先复用现有规则，除非用户明确要求重建或覆盖。

## 如何在外部资料目录里找资料

默认查找顺序：

1. 当前工程已有代码、`.ioc`、自动生成初始化文件。
2. `assets/example_catalog.json` 命中的最接近任务的例程，再去 `<materials-root>/examples/` 里展开少量目标文件。
3. `assets/book_catalog.json` 命中的教材章节，对应 `<materials-root>/textbook/` 中的教材 PDF。
4. `assets/book_excerpt_catalog.json` 命中的教材摘录、关键页和阅读提示。
5. `<materials-root>/pinout/` 中的引脚表和资源表。
6. `<materials-root>/board/` 中的原理图、连接图、板载资源说明。
7. `<materials-root>/datasheets/` 中的器件手册。

如果这些目录为空，明确告诉用户“当前资料目录还没补全，只能先给目录级建议和 HAL 通用方案”。

## ALIENTEK Example Filtering

当本地例程是典型 ALIENTEK HAL 目录结构时，不要盲扫整棵树，把它视为高噪声资料源，并按这个顺序读：

1. `.ioc`
2. `User/main.c`、`User/stm32f4xx_it.c`、`User/stm32f4xx_it.h`、`stm32f4xx_hal_msp.c`、`stm32f4xx_hal_conf.h`
3. CubeMX 风格模板里的 `Src/*.c` 和 `Inc/*.h`
4. `Drivers/BSP/<module>/*.c` 和 `*.h`
5. 只在任务明确命中时才看 `Drivers/SYSTEM/<module>`，例如 `usart`、`delay`、`sys`

默认忽略以下低价值目录，除非用户明确要看工具链、启动过程或厂商驱动内部：

- `Drivers/CMSIS/`
- `Drivers/STM32F4xx_HAL_Driver/`
- `Projects/MDK-ARM/`、`MDK-ARM/`、`RTE/`
- `Output/`、`Debug/`、`Release/`
- `*.uvprojx`、`*.uvoptx`、`*.axf`、`*.bin`、`*.hex`、`*.map`、`*.lst`

在 `<materials-root>/examples/` 上做手工 `rg` 之前，先运行：

```bash
python scripts/search_materials.py "<task>" --materials-root "<materials_root>" --format json
```

先读 `example_file_hits`，只有这些高信号命中仍不够时，才扩大搜索范围。

## 搜索与定位

优先使用快速搜索，而不是主观猜测：

- 在当前工程中搜索 `.ioc`、`MX_XXX_Init()`、`HAL_XXX_*Callback`、句柄和已有模块接口。
- 在例程中搜索目标模块名、外设名、外设实例、器件型号和关键宏。
- 对教材，先通过目录级索引定位章节，再按需读 PDF 对应页。
- 对 `<materials-root>/examples/`、`<materials-root>/pinout/`、`<materials-root>/board/` 优先使用 `rg --files` 和关键词搜索。

典型命令：

```bash
rg --files
rg -n "MX_.*_Init|HAL_.*Callback|huart|htim|hadc|hi2c|hspi" .
rg -n "oled|usart|uart|adc|dma|pwm|encoder|exti|ds18b20|dht11" <path>
```

## 硬约束

- 没有 `.ioc`、CubeMX 截图、或已生成的初始化证据时，不要假设底层已经配置正确。
- 不要伪造完整 `.ioc` 文件。可以给结构化的 CubeMX 配置建议清单。
- 不要默认 DMA stream/channel、GPIO AF、TIM 通道映射、ADC Rank、NVIC 已经正确。
- 不要把教材或例程的 Keil/MDK 工程壳直接搬进当前项目。
- 例程和教材用于迁移功能逻辑，不是最终工程模板。
- 修改 `stm32f4xx_it.c`、`stm32f4xx_hal_msp.c`、启动文件、链接脚本时要特别克制，只在任务确实需要且已有证据支持时才改。
- 若已有 `MX_XXX_Init()` 和句柄存在，优先在其基础上补应用层代码，而不是重写初始化。

## 输出要求

默认按以下结构回答，除非用户只要其中一部分：

### A. 项目判断

- 当前是否具备直接写代码的条件
- 缺什么证据
- 是否必须先回到 CubeMX

### B. 参考资料定位

- 应先看哪个本地例程
- 应先看教材哪一章、哪几页
- 是否必须看引脚表或板载资源表

### C. CubeMX 配置建议

- 外设与工作模式
- GPIO / AF
- DMA
- NVIC
- 时钟要求
- 特别注意事项

### D. 文件修改计划

- 新增哪些文件
- 修改哪些文件
- 每个文件承担什么职责

### E. 代码或补丁计划

- 给可直接接入当前 HAL 工程的代码，或明确给出 patch 计划
- 明确每段代码应放到哪个文件
- 明确依赖哪些句柄、宏或 `MX_XXX_Init()`

### F. 联调步骤

- 先看什么现象
- 再看什么变量、串口输出或波形
- 常见失败点按什么顺序排查

## Textbook Excerpts

如果 `assets/book_excerpt_catalog.json` 存在，不要只停在章节级定位。

在选出 `recommended_book_sections` 后，还要一并输出：

- `recommended_book_excerpts`
- 来源 PDF
- 页码范围
- 关键页
- 简短摘录或阅读提示

若摘录索引不存在，要明确说明当前只能做到章节级教材定位。

## 目标

你的目标不是泛泛解释 STM32 知识，而是：

- 快速定位当前任务该看哪个例程、哪个教材章节、哪几页。
- 明确告诉用户哪些必须先在 CubeMX 手工确认。
- 在已有工程证据足够时，把例程和教材中的功能逻辑迁移到当前 CubeMX HAL 工程。
- 准确规划 `Core/Inc + Core/Src` 结构下的多文件修改。
- 给出适合电赛现场的最小实现和最短排错路径。
