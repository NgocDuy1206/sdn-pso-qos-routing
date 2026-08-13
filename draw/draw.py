import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_qos_comparison(dij_file, pso_file, output_dir):
    # tạo folder nếu chưa có
    os.makedirs(output_dir, exist_ok=True)

    # đọc dữ liệu
    dij = pd.read_csv(dij_file)
    pso = pd.read_csv(pso_file)

    # đồng bộ độ dài
    min_len = min(len(dij), len(pso))
    dij = dij.iloc[:min_len]
    pso = pso.iloc[:min_len]

    time = dij["time_s"]

    # helper save (tự overwrite)
    def save_plot(filename):
        path = os.path.join(output_dir, filename)
        plt.savefig(path)
        plt.close()

    # ===== 1. Throughput =====
    plt.figure()
    plt.plot(time, dij["throughput_Mbps"], label="Dijkstra", linestyle='-')
    plt.plot(time, pso["throughput_Mbps"], label="PSO", linestyle='--')
    plt.xlabel("Time (s)")
    plt.ylabel("Throughput (Mbps)")
    plt.title("Throughput vs Time")
    plt.legend()
    plt.grid()
    save_plot("throughput.png")

    # ===== 2. Jitter =====
    plt.figure()
    plt.plot(time, dij["jitter_ms"], label="Dijkstra", linestyle='-')
    plt.plot(time, pso["jitter_ms"], label="PSO", linestyle='--')
    plt.xlabel("Time (s)")
    plt.ylabel("Jitter (ms)")
    plt.title("Jitter vs Time")
    plt.legend()
    plt.grid()
    save_plot("jitter.png")

    # ===== 3. Loss =====
    plt.figure()
    plt.plot(time, dij["loss"], label="Dijkstra", linestyle='-')
    plt.plot(time, pso["loss"], label="PSO", linestyle='--')
    plt.xlabel("Time (s)")
    plt.ylabel("Packet Loss")
    plt.title("Packet Loss vs Time")
    plt.legend()
    plt.grid()
    save_plot("loss.png")

    # ===== 4. Delay =====
    plt.figure()
    plt.plot(time, dij["delay_ms"], label="Dijkstra", linestyle='-')
    plt.plot(time, pso["delay_ms"], label="PSO", linestyle='--')
    plt.xlabel("Time (s)")
    plt.ylabel("Delay (ms)")
    plt.title("Delay vs Time")
    plt.legend()
    plt.grid()
    save_plot("delay.png")

    print(f"✅ Đã lưu biểu đồ vào: {output_dir}")


plot_qos_comparison("data/dij_f1.csv", "data/pso_f1.csv", "draw/flow1")
plot_qos_comparison("data/dij_f2.csv", "data/pso_f2.csv", "draw/flow2")