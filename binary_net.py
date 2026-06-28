#!/usr/bin/env python3
"""
binary_net.py — Full binary cosmic net.

Usage:
  python binary_net.py           # interactive curses viewer (6 restrictions)
  python binary_net.py --dump    # plain-text dump of all 6 restrictions
  python binary_net.py --machine # state machine transition table + demo traces
  python binary_net.py --graph   # cosmic graph demo with restriction propagation
"""

import argparse
from cosmic_network.binary.viewer import run, dump_all, dump_machine, dump_graph

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Binary Cosmic Net")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dump",    action="store_true", help="Plain-text restriction dump")
    group.add_argument("--machine", action="store_true", help="State machine transitions + demo")
    group.add_argument("--graph",   action="store_true", help="Graph propagation demo")
    args = parser.parse_args()

    if args.dump:
        dump_all()
    elif args.machine:
        dump_machine()
    elif args.graph:
        dump_graph()
    else:
        run()
