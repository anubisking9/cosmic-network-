"""
TikTok-style binary net viewer.

Controls (interactive mode):
  ↑ / ↓          scroll up/down within the current restriction
  ← / → or J/K   jump to previous/next restriction
  q               quit

Run with --dump for a plain-text print of all 6 restrictions.
"""

import curses
from .restrictions import RESTRICTIONS, Restriction, FULL, CONTEXTS
from .state import StateVector, PERM_NAMES, FULL_ACCESS
from .circuits import Circuit

_PAD_H = 130
_PAD_W = 120


# ── rendering ──────────────────────────────────────────────────────────────

def _render(pad: "curses.window", r: Restriction, idx: int, total: int) -> int:
    """Write a full restriction page onto *pad*. Returns number of lines used."""
    pad.clear()
    row = 0
    pw = _PAD_W

    def put(text: str = "", bold: bool = False) -> None:
        nonlocal row
        if row >= _PAD_H:
            return
        try:
            attr = curses.A_BOLD if bold else curses.A_NORMAL
            pad.addstr(row, 0, text[: pw - 1], attr)
        except curses.error:
            pass
        row += 1

    bar = "═" * 60

    # ── header ─────────────────────────────────────────────────────────
    put(f"  ╔{bar}╗")
    label = f"[{r.code}]  {r.name}"
    pager = f"[{idx + 1}/{total}]"
    put(f"  ║  {label:<46}{pager:>12}  ║", bold=True)
    put(f"  ╚{bar}╝")
    put()

    # ── state vector ───────────────────────────────────────────────────
    put("  ── STATE VECTOR ────────────────────────────────────────────────", bold=True)
    put(f"  FULL  {FULL.to_visual()}  0b{FULL.to_bits()}  ({FULL_ACCESS:3d})")
    put(f"  MASK  {r.state.to_visual()}  0b{r.state.to_bits()}  ({r.state.value:3d})")
    delta = FULL.XOR(r.state)
    put(f"  ΔXOR  {delta.to_visual()}  0b{delta.to_bits()}  ({delta.value:3d})")
    put()
    put(f"  {'BIT':<5} {'PERMISSION':<10} {'FULL':>4}  {'MASK':>4}  STATUS")
    put("  " + "─" * 42)
    for pos in range(7, -1, -1):
        f_v = "█" if FULL.get_bit(pos) else "░"
        m_v = "█" if r.state.get_bit(pos) else "░"
        status = "BLOCKED" if r.state.get_bit(pos) == 0 else "OPEN   "
        name = PERM_NAMES[pos].strip()
        put(f"  b{pos}    {name:<10} {f_v}      {m_v}     {status}")
    put()

    # ── logic circuit ──────────────────────────────────────────────────
    sym = {"AND": "∧", "OR": "∨", "XOR": "⊕", "NOT": "¬"}
    put(
        f"  ── LOGIC CIRCUIT  [ FULL_STATE  {r.circuit_op} ({sym.get(r.circuit_op,'?')})  MASK ] ────────────",
        bold=True,
    )
    circuit = Circuit(r.name, r.circuit_op, FULL, r.circuit_b)
    put(f"  {'BIT':<5}  IN_A   {r.circuit_op:<5}  IN_B   OUT")
    put("  " + "─" * 36)
    for i, (a, b, res) in enumerate(circuit.truth_rows()):
        pos = 7 - i
        a_v = "█" if a else "░"
        b_v = ("█" if b else "░") if b is not None else " "
        r_v = "█" if res else "░"
        put(f"  b{pos}      {a_v}    {r.circuit_op:<6} {b_v}      {r_v}")
    put()

    # ── binary signature ───────────────────────────────────────────────
    put("  ── BINARY SIGNATURE (16-bit: state ++ NOT state) ──────────────", bold=True)
    sig = r.signature
    vis_a = "".join("█" if b else "░" for b in sig[:8])
    vis_b = "".join("█" if b else "░" for b in sig[8:])
    bin_a = "".join(str(b) for b in sig[:8])
    bin_b = "".join(str(b) for b in sig[8:])
    put(f"  {vis_a}  {vis_b}")
    put(f"  {bin_a}  {bin_b}")
    put()

    # ── trigger mask ───────────────────────────────────────────────────
    put("  ── TRIGGER MASK ────────────────────────────────────────────────", bold=True)
    put(f"  {r.trigger_mask.to_visual()}  0b{r.trigger_mask.to_bits()}")
    trips = [PERM_NAMES[p].strip() for p in range(7, -1, -1) if r.trigger_mask.get_bit(p)]
    put(f"  TRIPS ON:  {' | '.join(trips) if trips else 'NONE'}")
    put()

    # ── permission matrix ──────────────────────────────────────────────
    perm_labels = ["READ", "WRIT", "SHAR", "CMNT", "DISC", "NTFY", "MONT", "LIVE"]
    put("  ── PERMISSION MATRIX  (rows=perms  cols=contexts) ─────────────", bold=True)
    put("          " + "  ".join(CONTEXTS))
    for perm_row, label in zip(r.perm_matrix, perm_labels):
        cells = "  ".join("█" if v else "░" for v in perm_row)
        put(f"  {label}    {cells}")
    put()

    # ── description ────────────────────────────────────────────────────
    put("  ── DESCRIPTION ─────────────────────────────────────────────────", bold=True)
    for line in r.description.split("\n"):
        put(f"  {line}")
    put()

    # ── nav hint ───────────────────────────────────────────────────────
    put("  " + "─" * 62)
    put("  ↑/↓ scroll   ◄/► or J/K switch restriction   Q quit")

    return row


# ── plain-text dump ────────────────────────────────────────────────────────

def dump_all() -> None:
    """Print all 6 restrictions to stdout (no curses required)."""
    total = len(RESTRICTIONS)
    for idx, r in enumerate(RESTRICTIONS):
        bar = "═" * 62
        print(f"\n  ╔{bar}╗")
        print(f"  ║  [{r.code}]  {r.name:<43} [{idx+1}/{total}]  ║")
        print(f"  ╚{bar}╝\n")

        # state vector
        delta = FULL.XOR(r.state)
        print("  STATE VECTOR")
        print(f"  FULL  {FULL.to_visual()}  0b{FULL.to_bits()}  ({FULL_ACCESS})")
        print(f"  MASK  {r.state.to_visual()}  0b{r.state.to_bits()}  ({r.state.value})")
        print(f"  ΔXOR  {delta.to_visual()}  0b{delta.to_bits()}  ({delta.value})\n")
        print(f"  {'BIT':<5} {'PERMISSION':<10} {'FULL':>4}  {'MASK':>4}  STATUS")
        print("  " + "─" * 42)
        for pos in range(7, -1, -1):
            f_v = "█" if FULL.get_bit(pos) else "░"
            m_v = "█" if r.state.get_bit(pos) else "░"
            status = "BLOCKED" if r.state.get_bit(pos) == 0 else "OPEN   "
            print(f"  b{pos}    {PERM_NAMES[pos].strip():<10} {f_v}      {m_v}     {status}")

        # circuit
        circuit = Circuit(r.name, r.circuit_op, FULL, r.circuit_b)
        print(f"\n  LOGIC CIRCUIT  [ FULL_STATE  {r.circuit_op}  MASK ]")
        print(f"  {'BIT':<5}  IN_A   {r.circuit_op:<5}  IN_B   OUT")
        print("  " + "─" * 36)
        for i, (a, b, res) in enumerate(circuit.truth_rows()):
            pos = 7 - i
            a_v = "█" if a else "░"
            b_v = ("█" if b else "░") if b is not None else " "
            r_v = "█" if res else "░"
            print(f"  b{pos}      {a_v}    {r.circuit_op:<6} {b_v}      {r_v}")

        # signature
        sig = r.signature
        vis_a = "".join("█" if b else "░" for b in sig[:8])
        vis_b = "".join("█" if b else "░" for b in sig[8:])
        bin_a = "".join(str(b) for b in sig[:8])
        bin_b = "".join(str(b) for b in sig[8:])
        print(f"\n  BINARY SIGNATURE (16-bit)")
        print(f"  {vis_a}  {vis_b}")
        print(f"  {bin_a}  {bin_b}")

        # trigger
        trips = [PERM_NAMES[p].strip() for p in range(7, -1, -1) if r.trigger_mask.get_bit(p)]
        print(f"\n  TRIGGER MASK")
        print(f"  {r.trigger_mask.to_visual()}  0b{r.trigger_mask.to_bits()}")
        print(f"  TRIPS ON:  {' | '.join(trips) if trips else 'NONE'}")

        # matrix
        perm_labels = ["READ", "WRIT", "SHAR", "CMNT", "DISC", "NTFY", "MONT", "LIVE"]
        print(f"\n  PERMISSION MATRIX  (rows=perms  cols=contexts)")
        print("          " + "  ".join(CONTEXTS))
        for perm_row, label in zip(r.perm_matrix, perm_labels):
            cells = "  ".join("█" if v else "░" for v in perm_row)
            print(f"  {label}    {cells}")

        # description
        print(f"\n  DESCRIPTION")
        for line in r.description.split("\n"):
            print(f"  {line}")
        print()


# ── interactive curses runner ──────────────────────────────────────────────

def run(dump: bool = False) -> None:
    if dump:
        dump_all()
        return

    def _main(stdscr: "curses.window") -> None:
        curses.curs_set(0)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()

        total = len(RESTRICTIONS)
        page = 0
        scroll = 0

        pad = curses.newpad(_PAD_H, _PAD_W)
        content_lines = _render(pad, RESTRICTIONS[page], page, total)

        while True:
            sh, sw = stdscr.getmaxyx()
            visible = sh - 1
            max_scroll = max(0, content_lines - visible)
            scroll = max(0, min(scroll, max_scroll))

            try:
                pad.refresh(scroll, 0, 0, 0, sh - 1, min(sw - 1, _PAD_W - 1))
            except curses.error:
                pass

            key = stdscr.getch()

            if key in (ord("q"), ord("Q")):
                break
            elif key == curses.KEY_DOWN:
                scroll = min(scroll + 1, max_scroll)
            elif key == curses.KEY_UP:
                scroll = max(scroll - 1, 0)
            elif key == curses.KEY_NPAGE or key == ord(" "):
                scroll = min(scroll + visible // 2, max_scroll)
            elif key == curses.KEY_PPAGE:
                scroll = max(scroll - visible // 2, 0)
            elif key in (curses.KEY_RIGHT, ord("J")):
                page = (page + 1) % total
                scroll = 0
                content_lines = _render(pad, RESTRICTIONS[page], page, total)
            elif key in (curses.KEY_LEFT, ord("K")):
                page = (page - 1) % total
                scroll = 0
                content_lines = _render(pad, RESTRICTIONS[page], page, total)

    try:
        curses.wrapper(_main)
    except Exception as exc:
        print(f"[curses unavailable: {exc}] — falling back to dump mode.\n")
        dump_all()
