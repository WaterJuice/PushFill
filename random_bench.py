#!/usr/bin/env python3
"""Fastest stdlib-only random byte generation — seed XOR counter, multiprocess."""

import ctypes
import os
import random
import sys
import time
from multiprocessing import Process
from multiprocessing import Value

CHUNK = 4 << 20  # 4 MiB per block
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 0  # 0 = run forever


def worker(counter, stop):
    base = int.from_bytes(random.randbytes(CHUNK), "little")
    stride = (1 << (CHUNK * 4)) | 0xDEADBEEF
    n = 0
    local = 0
    while not stop.value:
        (base ^ (stride * n)).to_bytes(CHUNK, "little")
        n += 1
        local += CHUNK
        counter.value = local


def main():
    ncpu = os.cpu_count() or 4
    print(f"seed^counter x{ncpu} processes, {CHUNK >> 20} MiB chunks")
    print("Ctrl+C to stop\n")

    counters = [Value(ctypes.c_uint64, 0, lock=False) for _ in range(ncpu)]
    stop = Value(ctypes.c_bool, False, lock=False)

    procs = []
    for i in range(ncpu):
        p = Process(target=worker, args=(counters[i], stop), daemon=True)
        p.start()
        procs.append(p)

    t0 = time.monotonic()
    prev_total = 0
    prev_time = t0

    def report():
        nonlocal prev_total, prev_time
        time.sleep(1.0)
        now = time.monotonic()
        total = sum(c.value for c in counters)
        dt = now - prev_time
        rate = (total - prev_total) / dt / 1e6
        avg = total / (now - t0) / 1e6
        print(
            f"  {rate:8.1f} MB/s  ({rate * 8 / 1e3:.2f} Gbps)"
            f"  |  avg {avg:.1f} MB/s ({avg * 8 / 1e3:.2f} Gbps)"
            f"  |  {total / 1e9:.2f} GB",
            flush=True,
        )
        prev_total = total
        prev_time = now

    def shutdown():
        stop.value = True
        for p in procs:
            p.join(timeout=2)
        elapsed = time.monotonic() - t0
        total = sum(c.value for c in counters)
        avg = total / elapsed / 1e6
        print(
            f"\n--- {total / 1e9:.2f} GB in {elapsed:.1f}s"
            f" — avg {avg:.1f} MB/s ({avg * 8 / 1e3:.2f} Gbps) ---"
        )

    try:
        if DURATION:
            deadline = t0 + DURATION
            while time.monotonic() < deadline:
                report()
            shutdown()
        else:
            while True:
                report()
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
