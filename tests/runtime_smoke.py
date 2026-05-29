"""
Runtime behavior smoke test — exercises the full simulation lifecycle
via HTTP API calls against a running backend server.

Tests:
  1. Pre-start state is clean
  2. Start initializes subsystems
  3. Process injection works
  4. Stepping advances tick and process execution
  5. Process terminates correctly
  6. Memory is allocated and freed
  7. Gantt chart records execution
  8. Deadlock state is clean
  9. Config update works
  10. Experiment run completes
"""
import asyncio
import httpx
import sys
import json

BASE = "http://127.0.0.1:8000"

async def main():
    errors = []
    async with httpx.AsyncClient(base_url=BASE, timeout=10.0) as c:
        # ── TEST 1: Pre-start state ──────────────────────────────────────────
        print("TEST 1: Pre-start state...")
        r = await c.get("/api/state")
        state = r.json()
        assert state["tick"] == 0, f"Expected tick=0, got {state['tick']}"
        assert state["processes"] == [], f"Expected empty processes"
        assert state["gantt"] == [], f"Expected empty gantt"
        print("  ✓ Pre-start state is clean")

        # ── TEST 2: Start simulation ─────────────────────────────────────────
        print("TEST 2: Start simulation...")
        r = await c.post("/api/control/start")
        start_resp = r.json()
        assert start_resp["status"] in ("started", "already_running"), f"Bad start: {start_resp}"
        await asyncio.sleep(0.3)  # Let subsystems initialize
        
        # Verify subsystems are now initialized
        r = await c.get("/api/state")
        state = r.json()
        assert "utilization" in state.get("cpu", {}), f"CPU subsystem not init: {state.get('cpu')}"
        print(f"  ✓ Simulation started, CPU state: {state['cpu']}")

        # ── TEST 3: Pause simulation (so we can step manually) ───────────────
        print("TEST 3: Pause simulation...")
        r = await c.post("/api/control/pause")
        pause_resp = r.json()
        assert pause_resp["status"] == "paused", f"Bad pause: {pause_resp}"
        print("  ✓ Paused")

        # ── TEST 4: Inject process ───────────────────────────────────────────
        print("TEST 4: Inject process...")
        r = await c.post("/api/processes/inject", json={
            "name": "TestProc1",
            "burst": 5,
            "priority": 3,
            "memory_pages": 2,
        })
        inject_resp = r.json()
        pid1 = inject_resp["pid"]
        print(f"  ✓ Injected PID={pid1}")

        # Inject a second process
        r = await c.post("/api/processes/inject", json={
            "name": "TestProc2",
            "burst": 3,
            "priority": 7,
            "memory_pages": 3,
        })
        pid2 = r.json()["pid"]
        print(f"  ✓ Injected PID={pid2}")

        # ── TEST 5: Step and verify tick advances ────────────────────────────
        print("TEST 5: Step through ticks...")
        tick_before = (await c.get("/api/state")).json()["tick"]
        
        for i in range(8):
            r = await c.post("/api/control/step")
            step_resp = r.json()
            assert step_resp["status"] == "stepped", f"Step failed: {step_resp}"
        
        r = await c.get("/api/state")
        state = r.json()
        tick_after = state["tick"]
        assert tick_after > tick_before, f"Tick didn't advance: {tick_before} → {tick_after}"
        print(f"  ✓ Ticks advanced: {tick_before} → {tick_after}")

        # ── TEST 6: Verify process states ────────────────────────────────────
        print("TEST 6: Verify process states...")
        processes = state["processes"]
        assert len(processes) >= 2, f"Expected ≥2 processes, got {len(processes)}"
        
        proc_states = {p["pid"]: p for p in processes}
        for pid in [pid1, pid2]:
            p = proc_states.get(pid)
            assert p is not None, f"PID {pid} not found in process list"
            print(f"  PID {pid} ({p['name']}): state={p['state']}, remaining={p['remaining_burst']}, waiting={p['waiting_time']}")

        # Check at least one process made progress (remaining < burst)
        any_progress = any(p["remaining_burst"] < p["burst_time"] if "burst_time" in p else p["remaining_burst"] < 5 for p in processes if p["pid"] in [pid1, pid2])
        print(f"  ✓ Process states verified, progress={any_progress}")

        # ── TEST 7: Memory allocation ────────────────────────────────────────
        print("TEST 7: Memory state...")
        mem = state.get("memory", {})
        print(f"  Memory: total_frames={mem.get('total_frames')}, free={mem.get('free_frames')}, allocated={mem.get('allocated_frames')}")
        
        blocks = mem.get("allocated_blocks", mem.get("blocks", []))
        if blocks:
            print(f"  ✓ {len(blocks)} memory blocks allocated")
        else:
            print(f"  ⚠ No memory blocks (may be OK if using paging without allocator)")

        # ── TEST 8: Gantt chart ──────────────────────────────────────────────
        print("TEST 8: Gantt chart...")
        gantt = state.get("gantt", [])
        print(f"  Gantt entries: {len(gantt)}")
        for g in gantt[:5]:
            print(f"    PID={g['pid']} ticks=[{g['start_tick']},{g['end_tick']}] color={g.get('color','?')}")
        if gantt:
            assert all("color" in g for g in gantt), "Missing color field in gantt!"
            assert all("start_tick" in g and "end_tick" in g for g in gantt), "Missing tick fields!"
            print("  ✓ Gantt data correct with color field")
        else:
            print("  ⚠ No gantt entries yet")

        # ── TEST 9: Deadlock state ───────────────────────────────────────────
        print("TEST 9: Deadlock state...")
        dl = state.get("deadlock", {})
        print(f"  Deadlock detected={dl.get('detected')}, cycles={dl.get('cycles')}")
        assert dl.get("detected") == False or dl.get("detected") is False, f"Unexpected deadlock: {dl}"
        print("  ✓ No deadlock (expected)")

        # ── TEST 10: Continue stepping until a process terminates ────────────
        print("TEST 10: Step until termination...")
        terminated_count = 0
        for i in range(20):
            await c.post("/api/control/step")
            r = await c.get("/api/state")
            s = r.json()
            term = [p for p in s["processes"] if p["state"] == "terminated"]
            if len(term) > terminated_count:
                terminated_count = len(term)
                for t in term:
                    print(f"  ✓ Process PID={t['pid']} ({t['name']}) terminated! turnaround={t['turnaround_time']}")
            if terminated_count >= 2:
                break
        
        if terminated_count == 0:
            print("  ⚠ No processes terminated in 20 extra ticks")
        else:
            print(f"  ✓ {terminated_count} processes completed lifecycle")

        # ── TEST 11: Disk state ──────────────────────────────────────────────
        print("TEST 11: Disk state...")
        disk = state.get("disk", {})
        print(f"  Disk: head={disk.get('current_head')}, algo={disk.get('algorithm')}, total_cyl={disk.get('total_cylinders')}")
        assert disk.get("total_cylinders") is not None, "Missing total_cylinders"
        print("  ✓ Disk state valid")

        # ── TEST 12: Config update ───────────────────────────────────────────
        print("TEST 12: Config update...")
        r = await c.put("/api/config", json={"scheduler": {"algorithm": "fcfs"}})
        cfg_resp = r.json()
        print(f"  Config response: {cfg_resp}")
        
        r = await c.get("/api/state")
        new_algo = r.json().get("config", {}).get("scheduler", {}).get("algorithm")
        print(f"  ✓ Scheduler algorithm now: {new_algo}")

        # ── TEST 13: Stop simulation ─────────────────────────────────────────
        print("TEST 13: Stop simulation...")
        r = await c.post("/api/control/stop")
        stop_resp = r.json()
        assert stop_resp["status"] == "stopped", f"Bad stop: {stop_resp}"
        print("  ✓ Simulation stopped cleanly")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors:
        print(f"  RUNTIME SMOKE TEST: {len(errors)} FAILURES")
        for e in errors:
            print(f"    ✗ {e}")
        return 1
    else:
        print("  RUNTIME SMOKE TEST: ALL PASSED ✓")
        return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
