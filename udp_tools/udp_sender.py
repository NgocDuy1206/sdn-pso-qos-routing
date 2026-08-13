# # udp_sender.py
# import socket
# import struct
# import time
# import sys

# if len(sys.argv) < 4:
#     print("Usage: python3 udp_sender.py <DST_IP> <PORT> <DURATION_SEC> [TARGET_BPS]")
#     print("Example: python3 udp_sender.py 10.0.0.2 5001 40 8000000")
#     sys.exit(1)

# DST_IP = sys.argv[1]
# PORT = int(sys.argv[2])
# DURATION = int(sys.argv[3])
# TARGET_BPS = int(sys.argv[4]) if len(sys.argv) > 4 else 10_000_000

# PACKET_SIZE = 1400

# sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# interval = (PACKET_SIZE * 8) / TARGET_BPS
# seq = 0
# start = time.perf_counter()
# next_send = start

# print(f"🚀 UDP Sender started → {DST_IP}:{PORT}")
# print(f"   Duration: {DURATION}s | Target: ~{TARGET_BPS/1_000_000:.1f} Mbps | Packet size: {PACKET_SIZE} bytes")

# while time.perf_counter() - start < DURATION:
#     send_time = time.perf_counter()

#     payload = struct.pack("!Id", seq, send_time)
#     payload += b'\x00' * (PACKET_SIZE - len(payload))

#     try:
#         sock.sendto(payload, (DST_IP, PORT))
#     except Exception as e:
#         print(f"Send error: {e}")
#         break

#     seq += 1

#     next_send += interval
#     now = time.perf_counter()
#     if next_send < now:
#         next_send = now
#     sleep_time = next_send - now
#     if sleep_time > 0:
#         time.sleep(sleep_time)

# print(f"✅ Sender finished after {DURATION} seconds. Total packets sent: {seq}")
import socket
import struct
import time
import sys

if len(sys.argv) < 4:
    print("Usage: python3 udp_sender.py <DST_IP> <PORT> <DURATION_SEC> [TARGET_BPS]")
    sys.exit(1)

DST_IP     = sys.argv[1]
PORT       = int(sys.argv[2])
DURATION   = int(sys.argv[3])
TARGET_BPS = int(sys.argv[4]) if len(sys.argv) > 4 else 10_000_000
PACKET_SIZE = 1400

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
interval = (PACKET_SIZE * 8) / TARGET_BPS

seq = 0
start = time.perf_counter()
next_send = start

print(f"🚀 UDP Sender → {DST_IP}:{PORT} | {DURATION}s | {TARGET_BPS/1_000_000:.1f} Mbps")

while time.perf_counter() - start < DURATION:
    send_time = time.time()          # ✅ wall clock để đo delay cross-host
    payload = struct.pack("!Id", seq, send_time)
    payload += b'\x00' * (PACKET_SIZE - len(payload))
    try:
        sock.sendto(payload, (DST_IP, PORT))
    except Exception as e:
        print(f"Send error: {e}")
        break

    seq += 1
    next_send += interval
    now = time.perf_counter()
    if next_send < now:
        next_send = now
    sleep_time = next_send - now
    if sleep_time > 0:
        time.sleep(sleep_time)

print(f"✅ Done. Sent: {seq} packets")