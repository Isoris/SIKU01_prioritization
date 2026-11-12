#!/usr/bin/env python3
"""SIKU01 candidate prioritization. Run `python prioritize.py --help` for the commands; README.md explains them."""
import sys

sys.dont_write_bytecode = True
from siku01_prioritization.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
