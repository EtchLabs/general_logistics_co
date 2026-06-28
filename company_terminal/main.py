#!/usr/bin/env python3
"""Launch the GLC Company Terminal — fullscreen Rich operations dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python main.py` from company_terminal/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from glc.app import run  # noqa: E402


if __name__ == "__main__":
    run()
