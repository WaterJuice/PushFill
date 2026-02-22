#!/usr/bin/env python3
"""Benchmark: data generation strategies for pushfill."""

import ctypes
import os
import random
import sys
import time
from multiprocessing import Process
from multiprocessing import Value

CHUNK = 4 << 20  # 4 MiB per block
BITS = CHUNK * 8
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 5


def worker_old(counter, stop):
    """Old approach: single seed XOR counter."""
    base = int.from_bytes(random.randbytes(CHUNK), "little")
    stride = (1 << (CHUNK * 4)) | 0x9E3779B97F4A7C15
    n = 0
    local = 0
    while not stop.value:
        (base ^ (stride * n)).to_bytes(CHUNK, "little")
        n += 1
        local += CHUNK
        counter.value = local


def worker_fresh_pair(counter, stop, pool_size):
    """Pool-based: XOR fresh random block with each other pool entry."""
    rng = random.Random()
    pool = []
    replace_idx = 0
    local = 0

    while not stop.value:
        # Generate a fresh random block
        val = rng.getrandbits(BITS)
        if len(pool) < pool_size:
            pool.append(val)
            fresh_idx = len(pool) - 1
        else:
            pool[replace_idx] = val
            fresh_idx = replace_idx
            replace_idx = (replace_idx + 1) % pool_size

        # Output the fresh block itself
        val.to_bytes(CHUNK, "little")
        local += CHUNK
        counter.value = local

        if stop.value:
            break

        # XOR fresh entry with every other pool entry
        for i in range(len(pool)):
            if i == fresh_idx:
                continue
            (pool[fresh_idx] ^ pool[i]).to_bytes(CHUNK, "little")
            local += CHUNK
            counter.value = local
            if stop.value:
                break


def run_bench(label, target, args_extra=(), duration=5):
    ncpu = os.cpu_count() or 4
    print(f"\n{label} x{ncpu} processes, {CHUNK >> 20} MiB chunks, {duration}s")

    counters = [Value(ctypes.c_uint64, 0, lock=False) for _ in range(ncpu)]
    stop = Value(ctypes.c_bool, False, lock=False)

    procs = []
    for i in range(ncpu):
        p = Process(
            target=target,
            args=(counters[i], stop, *args_extra),
            daemon=True,
        )
        p.start()
        procs.append(p)

    t0 = time.monotonic()
    prev_total = 0
    prev_time = t0

    deadline = t0 + duration
    while time.monotonic() < deadline:
        time.sleep(1.0)
        now = time.monotonic()
        total = sum(c.value for c in counters)
        dt = now - prev_time
        rate = (total - prev_total) / dt / 1e6
        avg = total / (now - t0) / 1e6
        print(
            f"  {rate:8.1f} MB/s  ({rate * 8 / 1e3:.2f} Gbps)"
            f"  |  avg {avg:.1f} MB/s ({avg * 8 / 1e3:.2f} Gbps)",
            flush=True,
        )
        prev_total = total
        prev_time = now

    stop.value = True
    for p in procs:
        p.join(timeout=2)
    elapsed = time.monotonic() - t0
    total = sum(c.value for c in counters)
    avg = total / elapsed / 1e6
    print(f"  => {total / 1e9:.2f} GB in {elapsed:.1f}s — avg {avg:.1f} MB/s")
    return avg


def main():
    dur = DURATION
    print(f"Benchmarking data generation strategies ({dur}s each)")

    results = {}

    results["seed^counter (old)"] = run_bench(
        "seed^counter (old)", worker_old, duration=dur
    )

    for pool_size in [4, 8, 16, 32]:
        label = f"fresh-pair pool({pool_size})"
        results[label] = run_bench(label, worker_fresh_pair, (pool_size,), duration=dur)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    baseline = results["seed^counter (old)"]
    for label, avg in results.items():
        pct = (avg / baseline - 1) * 100 if baseline > 0 else 0
        sign = "+" if pct >= 0 else ""
        print(f"  {label:30s}  {avg:8.1f} MB/s  ({sign}{pct:.1f}%)")


if __name__ == "__main__":
    main()
