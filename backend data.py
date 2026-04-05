import time

import numpy as np
import pandas as pd
import serial
from serial.tools import list_ports
import streamlit as st


SENSOR_COLUMNS = ["MQ3_Raw", "MQ135_Raw", "MQ2_Raw", "MQ9_Raw"]
SENSOR_LABELS = {
    "MQ3_Raw": "MQ-3",
    "MQ135_Raw": "MQ-135",
    "MQ2_Raw": "MQ-2",
    "MQ9_Raw": "MQ-9",
}
METHOD_OPTIONS = [
    "Baseline",
    "Moving Average",
    "Kalman",
    "Dynamic Adaptive Threshold",
    "Derivative",
    "Sensor Fusion",
]
SAMPLE_INTERVAL_SECONDS = 0.10


def ensure_streamlit_runtime() -> None:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
    except ImportError:
        return

    if get_script_run_ctx() is None:
        print("This app must be started with Streamlit.")
        print('Run: streamlit run "backend data.py"')
        raise SystemExit(0)


def init_state() -> None:
    if "data_history" not in st.session_state:
        st.session_state.data_history = pd.DataFrame(columns=["Time", "TS", *SENSOR_COLUMNS])
    if "is_running" not in st.session_state:
        st.session_state.is_running = False
    if "serial_conn" not in st.session_state:
        st.session_state.serial_conn = None
    if "total_packets" not in st.session_state:
        st.session_state.total_packets = 0
    if "valid_packets" not in st.session_state:
        st.session_state.valid_packets = 0
    if "rejected_spike_packets" not in st.session_state:
        st.session_state.rejected_spike_packets = 0
    if "serial_text_buffer" not in st.session_state:
        st.session_state.serial_text_buffer = ""
    if "last_valid_values" not in st.session_state:
        st.session_state.last_valid_values = None


def get_available_ports() -> list[str]:
    return [p.device for p in list_ports.comports()]


def connect_serial(port: str, baudrate: int):
    try:
        return serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
    except serial.SerialException as exc:
        st.error(f"无法连接到串口 {port}: {exc}")
        return None
    except Exception as exc:
        st.error(f"串口初始化异常: {exc}")
        return None


def close_serial() -> None:
    conn = st.session_state.serial_conn
    if conn is not None and conn.is_open:
        conn.close()
    st.session_state.serial_conn = None
    st.session_state.is_running = False


def parse_sensor_values(raw_line: str):
    if not raw_line:
        return None

    parts = [segment.strip() for segment in raw_line.split(",") if segment.strip()]
    if len(parts) < len(SENSOR_COLUMNS):
        return None

    values = []
    try:
        for token in parts[: len(SENSOR_COLUMNS)]:
            if ":" in token:
                token = token.split(":", 1)[1].strip()
            elif "=" in token:
                token = token.split("=", 1)[1].strip()
            values.append(float(token))
    except ValueError:
        return None

    return dict(zip(SENSOR_COLUMNS, values))


def read_serial_batch(conn: serial.Serial, max_lines: int = 200) -> list[dict[str, float]]:
    """Read only complete serial lines to avoid non-blocking partial-frame glitches."""
    parsed_rows: list[dict[str, float]] = []

    try:
        waiting = conn.in_waiting if hasattr(conn, "in_waiting") else 0
    except Exception:
        waiting = 0

    if waiting <= 0:
        return parsed_rows

    raw_chunks: list[bytes] = []
    loops = 0
    while loops < max_lines:
        try:
            if conn.in_waiting <= 0:
                break
            raw_chunks.append(conn.read(conn.in_waiting))
        except Exception:
            break
        loops += 1

    if not raw_chunks:
        return parsed_rows

    buffer_text = st.session_state.serial_text_buffer + b"".join(raw_chunks).decode("utf-8", errors="ignore")
    lines = buffer_text.split("\n")
    st.session_state.serial_text_buffer = lines[-1]
    complete_lines = lines[:-1]

    lines_read = 0
    for line in complete_lines:
        if lines_read >= max_lines:
            break

        raw_line = line.strip().rstrip("\r")
        if not raw_line:
            continue

        st.session_state.total_packets += 1
        value_map = parse_sensor_values(raw_line)
        if value_map is not None:
            if is_drop_spike(value_map, st.session_state.last_valid_values):
                st.session_state.rejected_spike_packets += 1
            else:
                st.session_state.valid_packets += 1
                parsed_rows.append(value_map)
                st.session_state.last_valid_values = value_map
        lines_read += 1

    return parsed_rows


def clear_serial_buffer(conn: serial.Serial) -> None:
    try:
        conn.reset_input_buffer()
    except Exception:
        pass
    st.session_state.serial_text_buffer = ""


def is_drop_spike(current_values: dict[str, float], last_values: dict[str, float] | None) -> bool:
    if not last_values:
        return False

    abrupt_drop_channels = 0
    for key in SENSOR_COLUMNS:
        previous = float(last_values.get(key, 0.0))
        current = float(current_values.get(key, 0.0))
        if previous <= 0.3:
            continue
        if current < previous * 0.45 and (previous - current) > 0.6:
            abrupt_drop_channels += 1

    return abrupt_drop_channels >= 2


def kalman_filter_series(series: pd.Series, process_noise: float, measurement_noise: float) -> pd.Series:
    if series.empty:
        return series

    estimate = float(series.iloc[0])
    error_est = 1.0
    output = []

    for measurement in series.astype(float):
        error_est += process_noise
        gain = error_est / (error_est + measurement_noise)
        estimate = estimate + gain * (measurement - estimate)
        error_est = (1.0 - gain) * error_est
        output.append(estimate)

    return pd.Series(output, index=series.index)


def estimate_timestamps(row_count: int) -> pd.DatetimeIndex:
    ts_now = pd.Timestamp.now()
    if row_count <= 1:
        return pd.DatetimeIndex([ts_now])
    return pd.date_range(
        end=ts_now,
        periods=row_count,
        freq=pd.to_timedelta(SAMPLE_INTERVAL_SECONDS, unit="s"),
    )


def compute_signal_features(df: pd.DataFrame, ma_window: int, baseline_window: int, adaptive_sigma: float) -> dict[str, pd.DataFrame]:
    features: dict[str, pd.DataFrame] = {}
    baseline = pd.DataFrame(index=df.index)
    moving_avg = pd.DataFrame(index=df.index)
    kalman = pd.DataFrame(index=df.index)
    derivative = pd.DataFrame(index=df.index)
    adaptive = pd.DataFrame(index=df.index)
    normalized = pd.DataFrame(index=df.index)
    activation = pd.DataFrame(index=df.index)

    for col in SENSOR_COLUMNS:
        series = df[col].astype(float)
        baseline_est = series.ewm(span=max(4, baseline_window), adjust=False).mean()
        residual = series - baseline_est
        robust_scale = (
            residual.abs().ewm(span=max(4, baseline_window), adjust=False).mean() * 1.4826
        ).clip(lower=1e-4)
        diff_std = series.diff().abs().rolling(window=max(3, ma_window), min_periods=2).mean().fillna(0.01)

        baseline[col] = residual
        moving_avg[col] = series.rolling(window=ma_window, min_periods=1).mean()
        kalman[col] = kalman_filter_series(
            series,
            process_noise=max(float(diff_std.median()) * 0.15, 0.001),
            measurement_noise=max(float(diff_std.median()) * 1.5, 0.01),
        )
        derivative[col] = (
            series.diff().div(SAMPLE_INTERVAL_SECONDS).rolling(window=3, min_periods=1).mean().fillna(0.0)
        )
        adaptive[col] = (residual - adaptive_sigma * robust_scale).clip(lower=0.0)
        normalized[col] = (residual / robust_scale).clip(lower=0.0).fillna(0.0)
        activation[col] = (adaptive[col] / robust_scale).clip(lower=0.0).fillna(0.0)

    fusion = pd.DataFrame(index=df.index)
    positive_derivative = derivative.clip(lower=0.0)
    fusion["MQ3_Raw"] = 0.70 * activation["MQ3_Raw"] + 0.30 * activation["MQ135_Raw"] + 0.08 * positive_derivative["MQ3_Raw"]
    fusion["MQ135_Raw"] = 0.20 * activation["MQ3_Raw"] + 0.60 * activation["MQ135_Raw"] + 0.20 * activation["MQ2_Raw"]
    fusion["MQ2_Raw"] = 0.15 * activation["MQ135_Raw"] + 0.55 * activation["MQ2_Raw"] + 0.30 * activation["MQ9_Raw"]
    fusion["MQ9_Raw"] = 0.10 * activation["MQ135_Raw"] + 0.35 * activation["MQ2_Raw"] + 0.55 * activation["MQ9_Raw"]

    features["Baseline"] = baseline
    features["Moving Average"] = moving_avg
    features["Kalman"] = kalman
    features["Dynamic Adaptive Threshold"] = adaptive
    features["Derivative"] = derivative
    features["Sensor Fusion"] = fusion
    features["Normalized"] = normalized
    features["Activation"] = activation
    return features


def classify_fingerprint(features: dict[str, pd.DataFrame]) -> tuple[str, dict[str, float]]:
    normalized = features["Normalized"]
    activation = features["Activation"]
    derivative = features["Derivative"]

    if normalized.empty:
        return "等待数据", {"Alcohol": 0.0, "Smoke": 0.0, "Air Quality": 0.0}

    latest_n = normalized.iloc[-1]
    latest_d = derivative.iloc[-1] if not derivative.empty else pd.Series(0.0, index=SENSOR_COLUMNS)

    latest_a = activation.iloc[-1]
    alcohol_score = (
        1.30 * float(latest_a["MQ3_Raw"])
        + 0.50 * float(latest_n["MQ135_Raw"])
        + 0.04 * max(float(latest_d["MQ3_Raw"]), 0.0)
    )
    smoke_score = (
        0.95 * float(latest_a["MQ2_Raw"])
        + 0.95 * float(latest_a["MQ9_Raw"])
        + 0.30 * float(latest_n["MQ135_Raw"])
        + 0.03 * max(float(latest_d["MQ2_Raw"]), 0.0)
    )
    air_score = (
        1.15 * float(latest_a["MQ135_Raw"])
        + 0.35 * float(latest_n["MQ2_Raw"])
        + 0.20 * float(latest_n["MQ9_Raw"])
    )

    scores = {
        "Alcohol": alcohol_score,
        "Smoke": smoke_score,
        "Air Quality": air_score,
    }
    label, top_score = max(scores.items(), key=lambda item: item[1])

    if top_score < 0.8:
        return "环境平稳", scores
    if label == "Alcohol":
        return "疑似酒精特征: MQ-3 主导上升，MQ-135 中等响应", scores
    if label == "Smoke":
        return "疑似烟雾/可燃气体特征: MQ-2 与 MQ-9 同步增强", scores
    return "疑似空气质量恶化: MQ-135 主导上升", scores


def estimate_health(df: pd.DataFrame) -> tuple[float, float, float]:
    total_packets = max(st.session_state.total_packets, 1)
    valid_packets = st.session_state.valid_packets
    packet_loss = max(0.0, min(1.0, (total_packets - valid_packets) / total_packets))

    if len(df) >= 8:
        signal = df["MQ3_Raw"].astype(float).rolling(8, min_periods=3).mean().iloc[-1]
        noise = df["MQ3_Raw"].astype(float).rolling(8, min_periods=3).std().iloc[-1]
        if pd.isna(noise) or noise <= 0:
            snr_db = 30.0
        else:
            snr_db = float(20.0 * np.log10(max(abs(signal), 1.0) / max(noise, 1e-6)))
    else:
        snr_db = 0.0

    snr_score = max(0.0, min(1.0, snr_db / 30.0))
    reliability = max(0.0, min(1.0, 0.70 * (1.0 - packet_loss) + 0.30 * snr_score))
    return reliability * 100.0, packet_loss * 100.0, snr_db


def build_sliding_window(df: pd.DataFrame, window_seconds: int = 10) -> pd.DataFrame:
    if df.empty:
        return df

    latest_ts = df["TS"].iloc[-1]
    window_start = latest_ts - pd.Timedelta(seconds=window_seconds)
    window_df = df[df["TS"] >= window_start].copy()
    if window_df.empty:
        return df.tail(1).copy()
    return window_df


def format_axis_time_index(ts_series: pd.Series) -> pd.Index:
    """Use explicit time labels so Streamlit x-axis always shows readable time."""
    ts = pd.to_datetime(ts_series, errors="coerce")

    if isinstance(ts, pd.DatetimeIndex):
        labels = pd.Series(ts).dt.strftime("%H:%M:%S.%f").str[:-3]
    else:
        labels = ts.dt.strftime("%H:%M:%S.%f").str[:-3]

    if labels.isna().any():
        fallback = pd.Series(ts_series).astype(str)
        labels = labels.fillna(fallback)

    return pd.Index(labels.astype(str))


ensure_streamlit_runtime()

st.set_page_config(page_title="Track A Gas Fingerprint Monitor", layout="wide")
st.title("Challenge 2 Track A: 多传感器气体指纹可视化")
st.caption("六种算法可切换查看，每种算法都显示 MQ-3、MQ-135、MQ-2、MQ-9 四条曲线。")

init_state()

st.sidebar.header("串口控制")
available_ports = get_available_ports()
default_port = available_ports[0] if available_ports else "COM9"

if available_ports:
    selected_port = st.sidebar.selectbox("检测到的串口", available_ports, index=0)
else:
    selected_port = default_port
    st.sidebar.warning("暂未检测到串口设备，请检查 USB 连接。")

port = st.sidebar.text_input("串口号", value=selected_port)
baudrate = st.sidebar.selectbox("波特率", [9600, 19200, 38400, 57600, 115200], index=4)
max_points = st.sidebar.slider("保留数据点数", 50, 1000, 240, 10)
refresh_ms = st.sidebar.slider("刷新间隔 (ms)", 50, 2000, 120, 10)
ma_window = st.sidebar.slider("滑动平均窗口", 3, 40, 8)
baseline_window = st.sidebar.slider("基线窗口", 5, 80, 20)
adaptive_sigma = st.sidebar.slider("动态阈值灵敏度", 0.5, 4.0, 1.8, 0.1)

btn_col1, btn_col2 = st.sidebar.columns(2)
if btn_col1.button("连接"):
    close_serial()
    st.session_state.serial_conn = connect_serial(port, baudrate)
    if st.session_state.serial_conn is not None and st.session_state.serial_conn.is_open:
        clear_serial_buffer(st.session_state.serial_conn)
if btn_col2.button("断开"):
    close_serial()

run_col1, run_col2 = st.sidebar.columns(2)
if run_col1.button("开始采集"):
    if st.session_state.serial_conn is not None and st.session_state.serial_conn.is_open:
        clear_serial_buffer(st.session_state.serial_conn)
        st.session_state.is_running = True
    else:
        st.warning("请先连接串口。")
if run_col2.button("停止采集"):
    st.session_state.is_running = False

if st.sidebar.button("清空历史"):
    st.session_state.data_history = pd.DataFrame(columns=["Time", "TS", *SENSOR_COLUMNS])
    st.session_state.total_packets = 0
    st.session_state.valid_packets = 0
    st.session_state.rejected_spike_packets = 0
    st.session_state.last_valid_values = None
    st.session_state.serial_text_buffer = ""

conn = st.session_state.serial_conn
if conn is not None and conn.is_open:
    st.sidebar.success(f"已连接: {port} @ {baudrate}")
else:
    st.sidebar.info("当前未连接串口")

if st.session_state.total_packets > 0:
    parse_rate = 100.0 * st.session_state.valid_packets / max(st.session_state.total_packets, 1)
    st.sidebar.caption(
        f"解析成功率: {parse_rate:.1f}% | 已过滤突降包: {st.session_state.rejected_spike_packets}"
    )

if st.session_state.is_running and conn is not None and conn.is_open:
    value_maps = read_serial_batch(conn)
    if value_maps:
        ts_index = estimate_timestamps(len(value_maps))
        new_rows = pd.DataFrame(value_maps)
        new_rows.insert(0, "TS", ts_index)
        new_rows.insert(0, "Time", new_rows["TS"].dt.strftime("%H:%M:%S.%f").str[:-3])

        st.session_state.data_history = pd.concat(
            [st.session_state.data_history, new_rows],
            ignore_index=True,
        ).iloc[-max_points:]

data_df = st.session_state.data_history.copy()

if data_df.empty:
    st.info("暂无数据，请连接串口并开始采集。")
else:
    data_df = data_df.reset_index(drop=True)
    window_df = build_sliding_window(data_df, window_seconds=10)
    features = compute_signal_features(
        data_df[SENSOR_COLUMNS],
        ma_window=ma_window,
        baseline_window=baseline_window,
        adaptive_sigma=adaptive_sigma,
    )

    method_choice = st.selectbox("选择查看算法", METHOD_OPTIONS, index=0)
    plot_df = features[method_choice].copy()
    plot_df = plot_df.iloc[window_df.index].copy()
    plot_df.rename(columns=SENSOR_LABELS, inplace=True)
    plot_df.index = format_axis_time_index(window_df["TS"])

    fingerprint_label, fingerprint_scores = classify_fingerprint(features)
    health_score, packet_loss_pct, snr_db = estimate_health(data_df)

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("当前方法", method_choice)
    metric_col2.metric("系统健康度", f"{health_score:.1f}%")
    metric_col3.metric("丢包率", f"{packet_loss_pct:.2f}%")
    metric_col4.metric("SNR", f"{snr_db:.2f} dB")

    chart_col, insight_col = st.columns([3, 2])

    with chart_col:
        st.subheader(f"{method_choice} 四传感器曲线")
        st.line_chart(plot_df, use_container_width=True)

        raw_plot = window_df[SENSOR_COLUMNS].rename(columns=SENSOR_LABELS).copy()
        raw_plot.index = format_axis_time_index(window_df["TS"])
        with st.expander("查看原始信号对照", expanded=False):
            st.line_chart(raw_plot, use_container_width=True)

        st.caption(
            f"当前显示最近 10 秒窗口: {window_df['TS'].iloc[0].strftime('%H:%M:%S')} - "
            f"{window_df['TS'].iloc[-1].strftime('%H:%M:%S')}"
        )

    with insight_col:
        st.subheader("气体指纹判断")
        if fingerprint_label == "环境平稳":
            st.success(fingerprint_label)
        else:
            st.warning(fingerprint_label)

        st.write(
            f"Alcohol 分数: {fingerprint_scores['Alcohol']:.2f}\n\n"
            f"Smoke 分数: {fingerprint_scores['Smoke']:.2f}\n\n"
            f"Air Quality 分数: {fingerprint_scores['Air Quality']:.2f}"
        )

        latest = data_df.iloc[-1]
        st.write(
            f"最新原始值: MQ-3={latest['MQ3_Raw']:.3f}, "
            f"MQ-135={latest['MQ135_Raw']:.3f}, "
            f"MQ-2={latest['MQ2_Raw']:.3f}, "
            f"MQ-9={latest['MQ9_Raw']:.3f}"
        )

        st.caption(
            "判定逻辑示例: 酒精更看重 MQ-3 + MQ-135；"
            "烟雾更看重 MQ-2 + MQ-9；空气质量恶化更看重 MQ-135。"
        )

    st.subheader("最近数据")
    preview = data_df[["Time", *SENSOR_COLUMNS]].tail(12).copy()
    preview.rename(columns=SENSOR_LABELS, inplace=True)
    st.dataframe(preview, use_container_width=True)

if st.session_state.is_running:
    time.sleep(refresh_ms / 1000.0)
    st.rerun()
