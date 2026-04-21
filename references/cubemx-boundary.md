# CubeMX 边界说明

明确哪些内容必须由用户在 CubeMX 中确认，哪些内容可以由 Codex 在现有 HAL 工程中直接实现。

## 总原则

- 代码必须围绕当前 `.ioc` 和已生成的 HAL 工程展开。
- 只要底层初始化是否正确会影响代码行为，就先要求用户确认 CubeMX 配置。
- 没有 `.ioc`、CubeMX 截图、`MX_XXX_Init()`、句柄定义等证据时，不要把建议说成既成事实。

## 什么时候先停在 CubeMX 配置建议

遇到以下任一情况，先输出 CubeMX 配置建议清单，再写代码：

- 时钟树、PLL、SYSCLK、APB 分频会影响功能结果。
- 需要启用或切换 GPIO 模式、上拉下拉、速度、AF。
- 需要启用 USART、I2C、SPI、ADC、TIM、DMA、CAN、FSMC、RTC、USB 等外设。
- 需要分配 DMA stream/channel/mode/direction。
- 需要启用 NVIC、EXTI、DMA 中断、外设全局中断。
- 需要确定 TIM 实例、Channel、PWM/输入捕获/编码器模式。
- 需要确定 ADC 通道、Rank、采样时间、触发源。
- 需要确认显示模块、传感器、通信模块的底层总线和板载资源占用。

## 可以直接写代码的前提证据

以下证据越完整，越可以直接在工程里补应用层代码：

- 存在 `.ioc` 文件。
- 已生成对应的 `MX_XXX_Init()`。
- 已存在句柄，如 `huart1`、`htim3`、`hadc1`、`hi2c1`、`hspi2`。
- 已存在 HAL 回调入口或 IRQHandler。
- 用户给出了 CubeMX 截图、引脚分配截图、时钟树截图。
- 工程里已经有目标外设相关的自动生成文件和 MSP 配置。

## 必须由用户在 CubeMX 中确认的内容

### 1. 芯片与工程基础设置

- 具体芯片型号
- Toolchain / IDE 生成选项
- 工程名与输出路径
- 是否重新生成、是否保留用户代码区

### 2. 时钟系统

- HSE / HSI / LSE / LSI
- PLL 参数
- SYSCLK / HCLK / PCLK
- 外设时钟来源
- 与波特率、PWM 频率、采样率、USB/CAN 相关的时钟约束

### 3. GPIO

- 引脚是否可用
- 引脚是否被板载资源占用
- Input / Output / AF / Analog 模式
- Pull-up / Pull-down / No pull
- Speed
- AF 映射
- 输出初始电平

### 4. 外设启用与工作模式

- USART / UART 实例与模式
- I2C 实例与速率
- SPI 实例与模式
- ADC 实例与通道
- TIM 实例、Channel 和工作模式
- CAN / USB / FSMC / RTC / SDIO 等复杂外设

### 5. DMA

- Stream
- Channel / Request
- 方向
- 普通 / 循环模式
- 数据宽度
- 优先级
- 与具体外设的绑定关系

### 6. NVIC / 中断

- 哪个中断源启用
- NVIC 优先级
- EXTI 线与 GPIO 的对应
- DMA 中断是否启用
- 外设全局中断是否启用

### 7. TIM / ADC 的细节

- TIM 的 Prescaler、Period、Counter Mode、PWM 通道
- ADC 的通道列表、Rank、Sampling Time、触发源、连续转换、扫描模式

## Codex 可以直接做的内容

- 新增 `Core/Inc/*.h` 与 `Core/Src/*.c` 模块文件。
- 在 `main.c` 中插入初始化调用、主循环逻辑和状态机。
- 编写 HAL 回调逻辑，如串口接收完成回调、EXTI 回调、定时器回调。
- 基于已存在的 `MX_XXX_Init()` 和句柄补业务代码。
- 把教材/例程中的驱动逻辑裁剪后迁移进当前工程。
- 给多文件补丁计划、联调步骤和排错顺序。
- 输出结构化 CubeMX 配置建议清单。

## 不要做的事

- 不要伪造完整 `.ioc` 文件。
- 不要默认时钟树已经正确。
- 不要默认某组 AF、DMA stream/channel、TIM channel 一定可用。
- 不要默认 NVIC 已打开。
- 不要默认教材或例程里的引脚能直接照搬到当前板子。
- 不要直接照搬 Keil/MDK 工程外壳。

## 建议输出模板

当任务卡在 CubeMX 边界时，优先按下面结构输出：

### CubeMX 配置建议

- 外设：
- 工作模式：
- GPIO / AF：
- DMA：
- NVIC：
- 时钟要求：
- 特别注意：

### 代码前提

- 若你已经生成了 `MX_XXX_Init()` 和对应句柄，下面代码可直接接入。
- 若尚未生成，先完成上面的 CubeMX 配置，再重新生成工程。

## 允许的合理推断

只有在以下情形下，才允许做“建议性推断”，并明确写成条件句：

- 用户明确给出了外设实例，如 “用 USART1”。
- 当前工程里已存在对应 `MX_XXX_Init()`。
- 用户提供了 `.ioc` 或截图，表明底层已启用。
- 当前任务只缺应用层逻辑，而底层初始化已经明显存在。

推荐写法：

- “如果你已经在 CubeMX 中启用 `USART1` 并生成了 `MX_USART1_UART_Init()`，下面代码可直接接入。”
- “如果 `ADC1 + DMA` 已在 `.ioc` 中配置完成，下面只补缓冲区和数据处理逻辑。”
