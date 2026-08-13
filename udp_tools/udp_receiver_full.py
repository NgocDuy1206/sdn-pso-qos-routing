
"""
UDP Receiver - throughput / delay / jitter / packet loss

Usage:
    python3 udp_receiver_full.py <PORT> [OUTPUT_CSV]

Sender packet format:
    seq       : uint32  (4 bytes)
    send_time : double  (8 bytes)
"""

import socket
import struct
import sys
import time
import csv
import os


if len(sys.argv) < 2:
    print("Usage: python3 udp_receiver_full.py <PORT> [OUTPUT_CSV]")
    sys.exit(1)

PORT   = int(sys.argv[1])
OUTPUT = sys.argv[2] if len(sys.argv) > 2 else "/tmp/udp_receiver_output.csv"

out_dir = os.path.dirname(OUTPUT)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", PORT))
sock.settimeout(2)

print(f" Listening on 0.0.0.0:{PORT}")
print(f" Output CSV: {OUTPUT}")


REPORT_INTERVAL = 0.5
IDLE_TIMEOUT    = 40
RESTART_GAP     = 100_000


highest_seq  = -1
base_seq     = None
prev_delay   = None
jitter_ewma  = 0.0


interval_seqs     = set()
interval_expected = 0
interval_received = 0
bytes_interval    = 0
delay_sum         = 0.0
pkt_interval      = 0


start_time       = time.perf_counter()
last_report      = start_time
last_packet_time = start_time


with open(OUTPUT, "w", newline="") as f:

    writer = csv.writer(f)
    writer.writerow([
        "timestamp", "time_s",
        "throughput_Mbps", "jitter_ms",
        "loss", "delay_ms"
    ])

    print("\n🚀 Receiving...\n")

    while True:

        try:
            data, _ = sock.recvfrom(65535)

        except socket.timeout:
            if time.perf_counter() - last_packet_time > IDLE_TIMEOUT:
                print(f"\n⏹  No traffic for {IDLE_TIMEOUT}s → stopped")
                break
            continue

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user")
            break

        recv_perf = time.perf_counter()
        recv_wall = time.time()
        last_packet_time = recv_perf


        if len(data) < 12:
            continue
        try:
            seq, send_time = struct.unpack("!Id", data[:12])
        except struct.error:
            continue


        if highest_seq != -1 and highest_seq - seq > RESTART_GAP:
            print(f"\n🔄 Sender restart detected (seq {highest_seq} → {seq})")
            highest_seq       = -1
            base_seq          = None
            interval_seqs.clear()
            interval_expected = 0
            interval_received = 0
            prev_delay        = None
            jitter_ewma       = 0.0


        if base_seq is None:
            base_seq = seq

        is_duplicate = seq in interval_seqs
        if not is_duplicate:
            interval_seqs.add(seq)

        if not is_duplicate and seq > highest_seq:
            interval_expected += 1 if highest_seq == -1 else seq - highest_seq
            highest_seq = seq


        delay_ms = (recv_wall - send_time) * 1000.0


        if not is_duplicate:
            if prev_delay is not None:
                d = abs(delay_ms - prev_delay)
                jitter_ewma += (d - jitter_ewma) / 16.0
            prev_delay = delay_ms

        if not is_duplicate:
            bytes_interval    += len(data)
            delay_sum         += delay_ms
            pkt_interval      += 1
            interval_received += 1


        if recv_perf - last_report >= REPORT_INTERVAL:

            interval_sec    = recv_perf - last_report
            throughput_mbps = bytes_interval * 8 / interval_sec / 1_000_000
            avg_delay       = delay_sum / pkt_interval if pkt_interval > 0 else 0.0
            elapsed         = recv_perf - start_time

            lost     = max(0, interval_expected - interval_received)
            loss_pct = lost / interval_expected * 100.0 if interval_expected > 0 else 0.0

            writer.writerow([
                round(time.time(), 3),      # timestamp
                round(elapsed, 3),          # time_s
                round(throughput_mbps, 3),  # throughput_Mbps
                round(jitter_ewma, 3),      # jitter_ms
                round(loss_pct, 3),         # loss
                round(avg_delay, 3),        # delay_ms
            ])
            f.flush()

            print(
                f"[{elapsed:7.1f}s] "
                f"BW={throughput_mbps:8.3f} Mbps | "
                f"Delay={avg_delay:8.3f} ms | "
                f"Jitter={jitter_ewma:7.3f} ms | "
                f"Loss={loss_pct:6.2f}% ({lost}/{interval_expected})"
            )

            # Reset interval (KHÔNG reset highest_seq, jitter_ewma, prev_delay)
            bytes_interval    = 0
            delay_sum         = 0.0
            pkt_interval      = 0
            interval_expected = 0
            interval_received = 0
            interval_seqs.clear()
            last_report = recv_perf
