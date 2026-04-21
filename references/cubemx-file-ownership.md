# CubeMX File Ownership

用这份规则区分“CubeMX 生成文件”和“用户业务代码文件”，避免 skill 在错误的位置动手。

## 默认判断原则

- `.ioc`
  视为 CubeMX 工程清单，只能在 CubeMX 里改，不应由模型手工伪造或大改。
- 带 `USER CODE BEGIN/END` 标记的 `main.c`、`stm32f4xx_it.c`、`stm32f4xx_hal_msp.c`、`gpio.c`、`usart.c`、`adc.c`、`tim.c` 等
  视为 CubeMX 生成文件，默认只允许改 `USER CODE` 区块。
- `Core/Inc/app_*.h`、`Core/Src/app_*.c`、`Core/Inc/bsp_*.h`、`Core/Src/bsp_*.c`
  默认视为用户可自由维护文件。
- `Drivers/CMSIS/`、`Drivers/STM32F4xx_HAL_Driver/`、`Middlewares/`
  视为厂商或框架代码，默认避免手工修改。

## 推荐做法

当 skill 扫到当前工程时，先回答这三件事：

1. 哪些文件是 CubeMX 管理的
2. 这些文件里哪些区块允许写
3. 哪些文件完全由用户业务层维护

如果工程不标准，允许用户在项目根目录放一个覆盖规则文件：

`stm32-cubemx-rules.json`

## 规则文件格式

```json
{
  "files": [
    {
      "path_glob": "Core/Src/main.c",
      "classification": "cubemx_generated",
      "generated_by": "cubemx",
      "editable_strategy": "user_sections_only",
      "notes": [
        "只允许改 USER CODE 区块",
        "不要改 SystemClock_Config 和 MX_XXX_Init 调用顺序"
      ]
    },
    {
      "path_glob": "Core/Src/app_uart.c",
      "classification": "user_owned",
      "generated_by": "user",
      "editable_strategy": "free_edit",
      "notes": [
        "这个文件由用户维护，可自由改"
      ]
    },
    {
      "path_glob": "Core/Src/usart.c",
      "classification": "cubemx_generated",
      "generated_by": "cubemx",
      "editable_strategy": "avoid_manual_edit",
      "notes": [
        "默认不要直接改，除非明确要求"
      ]
    }
  ]
}
```

## classification 建议值

- `cubemx_project_manifest`
- `cubemx_generated`
- `project_source`
- `user_owned`
- `vendor_or_framework`

## editable_strategy 建议值

- `edit_in_cubemx_only`
  只能回到 CubeMX 调整。
- `user_sections_only`
  只允许在 `USER CODE BEGIN/END` 区块写代码。
- `avoid_manual_edit`
  默认避免手工修改，除非用户明确要求并接受风险。
- `free_edit`
  可直接改。

## skill 中的使用方式

当 `scan_current_project.py` 输出：

- `management_by_file`
- `management_summary`
- `editable_summary`

时，优先按这些字段决定落点。

解释时要明确说：

- 哪些文件只能在 CubeMX 里改
- 哪些文件只能改 `USER CODE`
- 哪些文件适合新增业务模块和长期维护
