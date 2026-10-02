"""Executable module entrypoint for python -m cert_coach."""

from __future__ import annotations

import sys
from cert_coach.cli import main

if __name__ == "__main__":
    sys.exit(main())
