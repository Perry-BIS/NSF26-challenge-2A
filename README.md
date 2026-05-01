# NSF26 Challenge 2A

[中文](#zh) | [English](#en)

---

<a id="zh"></a>

## 中文说明

### 项目简介

本项目是一个基于 `Streamlit` 的气体传感器监测与分析系统，用于采集、显示和处理 4 路 MQ 系列气体传感器数据。系统通过串口与硬件设备通信，并提供多种信号处理方法，便于实时观察传感器响应和分析气体特征。

### 主要功能

- 实时串口数据采集
- 4 路 MQ 传感器数据可视化
- 多种信号处理算法切换
- 历史数据记录与基础统计
- 异常尖峰/突降数据过滤
- 适合课堂演示、原型验证和快速实验

### 支持的传感器

- `MQ-3`: 酒精检测
- `MQ-135`: 空气质量检测
- `MQ-2`: 烟雾 / 可燃气体检测
- `MQ-9`: 一氧化碳 / 可燃气体检测

### 内置处理方法

应用和固件中涉及的处理方法包括：

1. `Baseline`
2. `Moving Average`
3. `Kalman`
4. `Dynamic Adaptive Threshold`
5. `Derivative`
6. `Sensor Fusion`

### 项目结构

```text
NSF26-challenge-2A/
|- backend data.py      # Streamlit 数据采集与分析界面
|- sketch_apr1a.ino     # Arduino / ADS1115 采集固件
|- README.md            # 双语说明文档
|- Insight.pptx         # 项目展示材料
`- Insight-final(1).pptx
```

### 环境要求

- Python 3.8+
- Windows / macOS / Linux
- 可用串口设备

### 安装依赖

```bash
pip install streamlit pandas numpy pyserial
```

### 启动方式

```bash
streamlit run "backend data.py"
```

启动后通常可在浏览器中访问：

```text
http://localhost:8501
```

### 基本使用流程

1. 连接硬件并确认串口可见。
2. 运行 `streamlit run "backend data.py"`。
3. 在页面中选择串口与波特率。
4. 开始实时采集数据。
5. 切换不同处理方法并观察传感器变化。

### 串口输出说明

Arduino 固件会输出类似下面的串口文本：

```text
MQ3:...,MQ135:...,MQ2:...,MQ9:...,MODE:...,ACTIVE_MQ3:...,FPRINT:...,FUSED_MQ3:...
```

当前 Python 应用主要读取前 4 个原始传感器值：

- `MQ3`
- `MQ135`
- `MQ2`
- `MQ9`

### 常见问题

**1. 无法连接串口**

- 检查硬件是否已正确连接
- 检查所选串口号是否正确
- 检查波特率是否与固件一致
- 确认串口未被其他程序占用

**2. 页面提示 `This app must be started with Streamlit.`**

请使用：

```bash
streamlit run "backend data.py"
```

不要直接执行：

```bash
python "backend data.py"
```

**3. 数据看起来不稳定**

- 检查接线和供电稳定性
- 适当增加预热时间
- 尝试切换不同处理方法比较效果

### 说明

本仓库包含用于 NSF26 Challenge 2A 的原型代码、固件和展示材料。

---

<a id="en"></a>

## English

### Overview

This project is a `Streamlit`-based gas sensor monitoring and analysis system for collecting, displaying, and processing data from four MQ-series gas sensors. It communicates with the hardware over a serial port and provides multiple signal-processing methods for real-time observation and gas-response analysis.

### Features

- Real-time serial data acquisition
- Visualization for four MQ sensor channels
- Multiple signal-processing modes
- Historical data tracking and basic statistics
- Spike / abrupt-drop filtering
- Useful for demos, prototyping, and rapid experiments

### Supported Sensors

- `MQ-3`: Alcohol sensing
- `MQ-135`: Air quality sensing
- `MQ-2`: Smoke / combustible gas sensing
- `MQ-9`: Carbon monoxide / combustible gas sensing

### Built-in Processing Methods

The app and firmware include or reference these methods:

1. `Baseline`
2. `Moving Average`
3. `Kalman`
4. `Dynamic Adaptive Threshold`
5. `Derivative`
6. `Sensor Fusion`

### Repository Structure

```text
NSF26-challenge-2A/
|- backend data.py      # Streamlit data collection and analysis UI
|- sketch_apr1a.ino     # Arduino / ADS1115 acquisition firmware
|- README.md            # Bilingual project documentation
|- Insight.pptx         # Presentation material
`- Insight-final(1).pptx
```

### Requirements

- Python 3.8+
- Windows / macOS / Linux
- An available serial device

### Install Dependencies

```bash
pip install streamlit pandas numpy pyserial
```

### Run the App

```bash
streamlit run "backend data.py"
```

The app will usually be available at:

```text
http://localhost:8501
```

### Basic Workflow

1. Connect the hardware and confirm the serial port is available.
2. Run `streamlit run "backend data.py"`.
3. Select the serial port and baud rate in the UI.
4. Start real-time data acquisition.
5. Switch processing methods and inspect sensor behavior.

### Serial Output Format

The Arduino firmware emits serial lines similar to:

```text
MQ3:...,MQ135:...,MQ2:...,MQ9:...,MODE:...,ACTIVE_MQ3:...,FPRINT:...,FUSED_MQ3:...
```

The current Python app primarily reads the first four raw sensor values:

- `MQ3`
- `MQ135`
- `MQ2`
- `MQ9`

### Troubleshooting

**1. Cannot connect to the serial port**

- Verify the hardware connection
- Make sure the selected port is correct
- Confirm the baud rate matches the firmware
- Ensure no other program is using the port

**2. The app shows `This app must be started with Streamlit.`**

Use:

```bash
streamlit run "backend data.py"
```

Do not run:

```bash
python "backend data.py"
```

**3. The data looks unstable**

- Check wiring and power stability
- Allow the sensors enough warm-up time
- Compare different processing methods

### Notes

This repository contains prototype code, firmware, and presentation assets for NSF26 Challenge 2A.
