# NSF26 Challenge 2A - 气体传感器监测系统

## 项目概述

本项目是一个基于 Streamlit 的气体传感器监测系统，支持实时收集、处理和分析来自多个 MQ 系列气体传感器的数据。该系统通过串口通信与硬件设备连接，并提供多种数据处理和可视化方法。

## 功能特性

### 传感器支持
- **MQ-3**：酒精气体传感器
- **MQ-135**：空气质量传感器
- **MQ-2**：烟雾/液化气传感器
- **MQ-9**：一氧化碳/可燃气传感器

### 数据处理方法
系统提供多种数据处理算法：
1. **Baseline** - 基线方法
2. **Moving Average** - 移动平均滤波
3. **Kalman** - 卡尔曼滤波
4. **Dynamic Adaptive Threshold** - 动态自适应阈值
5. **Derivative** - 微分方法
6. **Sensor Fusion** - 传感器融合

### 主要功能
- ✅ 实时串口数据采集
- ✅ 多传感器数据融合处理
- ✅ 数据历史记录与统计分析
- ✅ 异常值检测与处理
- ✅ 可视化数据展示
- ✅ 采样间隔可配置（默认 0.1 秒）

## 安装说明

### 系统要求
- Python 3.8+
- Windows/macOS/Linux

### 依赖包安装

```bash
pip install streamlit pandas numpy pyserial
```

### 所需库说明
- **streamlit**: Web 应用框架
- **pandas**: 数据处理和分析
- **numpy**: 数值计算
- **pyserial**: 串口通信

## 使用方法

### 启动应用

```bash
streamlit run "backend data.py"
```

应用将在浏览器中自动打开，通常访问地址为 `http://localhost:8501`

### 基本流程

1. **选择串口**: 从可用串口列表中选择连接硬件的串口
2. **配置波特率**: 设置与硬件匹配的波特率（需与硬件配置一致）
3. **启动数据采集**: 点击开始按钮开始实时数据收集
4. **选择处理方法**: 选择合适的数据处理算法
5. **查看分析结果**: 实时查看传感器数据和处理结果

## 项目结构

```
challenge 2 track A/
├── backend data.py       # 主程序文件
├── README.md            # 项目说明文档（本文件）
└── __pycache__/         # Python 缓存目录
```

## 关键模块说明

### 核心函数

- `ensure_streamlit_runtime()` - 验证 Streamlit 运行环境
- `init_state()` - 初始化会话状态
- `connect_serial()` - 建立串口连接
- `read_serial_batch()` - 批量读取串口数据
- `parse_sensor_values()` - 解析传感器数据

### 数据格式

传感器数据包含以下列：
- `Time` - 本地时间戳
- `TS` - 系统时间戳
- `MQ3_Raw` - MQ-3 原始值
- `MQ135_Raw` - MQ-135 原始值
- `MQ2_Raw` - MQ-2 原始值
- `MQ9_Raw` - MQ-9 原始值

## 技术特点

### 数据采集优化
- 非阻塞式串口读取
- 完整数据行解析机制
- 自动异常值检测与过滤

### 可靠性特性
- 异常抖动检测
- 数据包验证
- 丢弃率统计

## 故障排除

### 常见问题

**Q: 无法连接到串口**
- 确保硬件设备正确连接
- 检查串口号是否正确
- 检查波特率设置是否与硬件匹配
- 确保没有其他程序占用该串口

**Q: 数据读取不稳定**
- 检查接线是否良好
- 调整采样间隔时间
- 尝试不同的数据处理方法

**Q: 显示 "This app must be started with Streamlit"**
- 必须使用 `streamlit run` 命令启动应用
- 不能直接用 Python 运行 `backend data.py`

## 要求与兼容性

- 支持标准 UART/USB 串口设备
- 支持 Windows、macOS 和 Linux
- 需要有效的串口连接

## 许可证

NSF26 Challenge 2A

## 贡献

欢迎提交 Issue 和 Pull Request！

---

**最后更新**: 2026 年 4 月
