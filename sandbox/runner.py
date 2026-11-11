"""Basic Python sandbox: run short analysis scripts in a separate process.

Protections: import whitelist, blocked dangerous builtins (checked before running),
separate process, timeout, no API keys in the environment, output size limit.
This is NOT a full security boundary. A Docker container is the production-grade next step.
"""
import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ALLOWED_MODULES = {
    "math", "statistics", "json", "datetime", "random", "decimal", "fractions",
    "itertools", "collections", "functools", "numpy", "pandas",
}
BLOCKED_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "exit", "quit",
}
TIMEOUT_SECONDS = 15
MAX_OUTPUT_CHARS = 6000


def validate(code: str) -> str | None:
    """Return an error message if the code is not allowed, otherwise None."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"SyntaxError: {e}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_MODULES:
                    return f"import of '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in ALLOWED_MODULES:
                return f"import from '{node.module}' is not allowed"
        elif isinstance(node, ast.Name) and node.id in BLOCKED_NAMES:
            return f"use of '{node.id}' is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            return f"access to '{node.attr}' is not allowed"
    return None


def run_python(code: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    """Run code in a separate Python process. Returns stdout, stderr and status."""
    error = validate(code)
    if error:
        return {"ok": False, "stdout": "", "stderr": f"Blocked by sandbox: {error}", "timed_out": False}

    # Minimal environment: no API keys or other secrets are passed to the script.
    env = {k: os.environ[k] for k in ("SYSTEMROOT", "PATH") if k in os.environ}

    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "script.py"
        script.write_text(code, encoding="utf-8")
        try:
            # stdin=DEVNULL is important: when this runs inside the MCP server, the server's
            # stdin is a pipe, and inheriting it can make the child process hang on Windows.
            proc = subprocess.run(
                [sys.executable, "-I", str(script)],
                cwd=tmp,
                env=env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": f"Timed out after {timeout}s", "timed_out": True}

    return {
        "ok": proc.returncode == 0,
        "stdout": proc.stdout[:MAX_OUTPUT_CHARS],
        "stderr": proc.stderr[:MAX_OUTPUT_CHARS],
        "timed_out": False,
    }