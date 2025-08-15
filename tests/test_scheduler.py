from services.scheduler import Scheduler


def test_scheduler_runs_due_jobs_and_records_state():
    calls = []
    t = [0.0]

    def time_fn():
        return t[0]

    def sleep_fn(s):
        t[0] += s

    def job_a():
        calls.append("a")

    sched = Scheduler(time_fn=time_fn, sleep_fn=sleep_fn)
    sched.add_interval_job("job_a", job_a, seconds=5, start_immediately=True)

    # first run (due immediately)
    sched.run_loop(once=True)
    assert calls == ["a"]

    # advance less than interval - no run
    t[0] += 4
    sched.run_loop(once=True)
    assert calls == ["a"]

    # advance past interval - second run
    t[0] += 2
    sched.run_loop(once=True)
    assert calls == ["a", "a"]

    state = sched.jobs_state()[0]
    assert state["run_count"] == 2
    assert state["name"] == "job_a"
    assert state["interval_sec"] == 5
