"""Sandbox tests. They run real subprocesses but need no network."""
from sandbox import runner


def test_simple_calculation():
    result = runner.run_python("print(2000 * 1.1 ** 5)")
    assert result["ok"] and result["stdout"].startswith("3221.02")


def test_blocked_import():
    result = runner.run_python("import os")
    assert not result["ok"] and "not allowed" in result["stderr"]


def test_blocked_open():
    result = runner.run_python("open('x.txt')")
    assert not result["ok"] and "not allowed" in result["stderr"]


def test_timeout():
    result = runner.run_python("while True: pass", timeout=2)
    assert result["timed_out"]