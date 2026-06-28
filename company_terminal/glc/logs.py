from __future__ import annotations

import subprocess
import threading
from collections import deque
from pathlib import Path
from typing import Callable


class DockerLogTailer:
    """Stream docker compose logs for a single service in a background thread."""

    def __init__(self, compose_file: Path, project_name: str) -> None:
        self.compose_file = compose_file
        self.project_name = project_name
        self._process: subprocess.Popen[str] | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._service: str | None = None
        self._on_line: Callable[[str], None] | None = None

    def start(self, service: str, on_line: Callable[[str], None], tail: int = 120) -> None:
        self.stop()
        self._service = service
        self._on_line = on_line
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(service, tail), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._process = None
        self._thread = None

    def _run(self, service: str, tail: int) -> None:
        cmd = [
            "docker",
            "compose",
            "-f",
            str(self.compose_file),
            "-p",
            self.project_name,
            "logs",
            "-f",
            "--tail",
            str(tail),
            service,
        ]
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            if self._on_line:
                self._on_line("[red]docker not found — log streaming unavailable[/]")
            return

        assert self._process.stdout is not None
        for line in self._process.stdout:
            if self._stop.is_set():
                break
            if self._on_line and line:
                self._on_line(line.rstrip())
        if self._process.poll() is None:
            self._process.terminate()


class LogBuffer:
    """Ring buffer for log lines when not actively viewing the logs tab."""

    def __init__(self, maxlen: int = 500) -> None:
        self._lines: deque[str] = deque(maxlen=maxlen)

    def append(self, line: str) -> None:
        self._lines.append(line)

    def clear(self) -> None:
        self._lines.clear()

    def lines(self) -> list[str]:
        return list(self._lines)
