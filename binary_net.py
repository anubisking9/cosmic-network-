#!/usr/bin/env python3
"""
binary_net.py — Full binary cosmic net.

Usage:
  python binary_net.py          # interactive curses viewer
  python binary_net.py --dump   # plain-text dump of all 6 restrictions
"""

import argparse
from cosmic_network.binary.viewer import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binary Cosmic Net viewer")
    parser.add_argument(
        "--dump",
        action="store_true",
        help="Print all restrictions to stdout (no interactive UI)",
    )
    args = parser.parse_args()
    run(dump=args.dump)
