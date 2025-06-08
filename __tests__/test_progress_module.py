from src import progress


def test_progress_tracking():
    progress.job_tasks.clear()
    progress.bind_job("abc")
    progress.report("step")
    assert progress.job_tasks["abc"] == "step"
    progress.clear_job()
    assert "abc" not in progress.job_tasks
