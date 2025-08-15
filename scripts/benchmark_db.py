"""Quick benchmark comparing individual get_connection calls vs single transaction batching.

Run directly: python scripts/benchmark_db.py
Outputs approximate timings; not a rigorous microbenchmark.
"""
from __future__ import annotations
import time
from data.db import get_connection, transaction, init_db

N = 500

def bench_individual(n: int) -> float:
    t0 = time.perf_counter()
    for i in range(n):
        with get_connection() as conn:
            conn.execute("INSERT INTO events(timestamp, agent, event_type, payload) VALUES (?,?,?,?)", (str(i),"bench","tick", str(i)))
    return time.perf_counter() - t0

def bench_batched(n: int) -> float:
    t0 = time.perf_counter()
    with transaction() as conn:
        for i in range(n):
            conn.execute("INSERT INTO events(timestamp, agent, event_type, payload) VALUES (?,?,?,?)", (str(i),"bench","tick", str(i)))
    return time.perf_counter() - t0

if __name__ == "__main__":
    init_db()
    # Clear table
    with get_connection() as c:
        c.execute("DELETE FROM events")
        c.commit()
    t_ind = bench_individual(N)
    with get_connection() as c:
        c.execute("DELETE FROM events")
        c.commit()
    t_batch = bench_batched(N)
    print({"rows": N, "individual_sec": round(t_ind,4), "batched_sec": round(t_batch,4), "speedup_x": round(t_ind / t_batch if t_batch else 0.0, 2)})
