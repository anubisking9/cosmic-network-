"""
Restriction state machine.

Every state is a StateVector.  Every transition is a bitwise operation.
Triggers are human-readable labels; the gate does the actual work.

Transition format:
  new_state = current_state  <OP>  mask

Where OP is AND (tightening) or XOR (partial lift/shift) or OR (restoring).
"""

from dataclasses import dataclass
from .state import StateVector, FULL_ACCESS
from .circuits import Circuit
from .restrictions import (
    RESTRICTIONS, SHADOW_BAN, CONTENT_FILTER, RATE_LIMIT,
    GEO_BLOCK, AGE_GATE, REACH_THROTTLE, FULL,
)

NORMAL = StateVector(FULL_ACCESS)   # unconstrained state


@dataclass(frozen=True)
class Transition:
    from_state: str
    to_state: str
    trigger: str         # human-readable condition
    op: str              # AND / OR / XOR
    mask: StateVector    # second operand

    def apply(self, current: StateVector) -> StateVector:
        c = Circuit(self.trigger, self.op, current, self.mask)
        return c.result

    def visual_row(self) -> str:
        before_sym = "████████" if self.from_state == "NORMAL" else ""
        arrow = f"──({self.trigger})──{self.op} {self.mask.to_visual()}──→"
        return f"  {self.from_state:<18} {arrow}  {self.to_state}"


# ── per-transition XOR/AND/OR masks — each chosen so that:
#    t.apply(from_state_sv) == to_state_sv  exactly
# ──────────────────────────────────────────────────────────────────────────────

# CONTENT_FILTER (0b11011111) → SHADOW_BAN (0b11010011) via XOR
# delta = 0b11011111 XOR 0b11010011 = 0b00001100
_CF_TO_SB = CONTENT_FILTER.state.XOR(SHADOW_BAN.state)      # 0b00001100

# RATE_LIMIT (0b11111110) → SHADOW_BAN (0b11010011) via XOR
# delta = 0b11111110 XOR 0b11010011 = 0b00101101
_RL_TO_SB = RATE_LIMIT.state.XOR(SHADOW_BAN.state)          # 0b00101101

# SHADOW_BAN (0b11010011) → REACH_THROTTLE (0b11110111) via XOR
# delta = 0b11010011 XOR 0b11110111 = 0b00100100
_SB_TO_RT = SHADOW_BAN.state.XOR(REACH_THROTTLE.state)      # 0b00100100

# lift masks: OR with the bits that were blocked to restore them
_AG_LIFT = AGE_GATE.trigger_mask         # 0b01110111
_RT_LIFT = REACH_THROTTLE.trigger_mask   # 0b00001000
_CF_LIFT = CONTENT_FILTER.trigger_mask   # 0b00100000
_RL_LIFT = RATE_LIMIT.trigger_mask       # 0b00000001


TRANSITIONS: list[Transition] = [
    # ── tighten from NORMAL (AND works; NORMAL = all-1s so AND always exact) ──
    Transition("NORMAL",         "CONTENT_FILTER", "classifier_trip",  "AND", CONTENT_FILTER.state),
    Transition("NORMAL",         "RATE_LIMIT",     "bucket_overflow",  "AND", RATE_LIMIT.state),
    Transition("NORMAL",         "AGE_GATE",       "kyc_missing",      "AND", AGE_GATE.state),
    Transition("NORMAL",         "GEO_BLOCK",      "geo_match",        "AND", GEO_BLOCK.state),
    # ── tighten via XOR-delta (from-state already has bits cleared, AND insufficient) ─
    Transition("CONTENT_FILTER", "SHADOW_BAN",     "repeat_violation", "XOR", _CF_TO_SB),
    Transition("RATE_LIMIT",     "SHADOW_BAN",     "limit_persists",   "XOR", _RL_TO_SB),
    Transition("SHADOW_BAN",     "GEO_BLOCK",      "geo_escalate",     "AND", GEO_BLOCK.state),
    # ── partial lift ────────────────────────────────────────────────────
    Transition("SHADOW_BAN",     "REACH_THROTTLE", "appeal_partial",   "XOR", _SB_TO_RT),
    # ── restore ─────────────────────────────────────────────────────────
    Transition("AGE_GATE",       "NORMAL",         "kyc_cleared",      "OR",  _AG_LIFT),
    Transition("REACH_THROTTLE", "NORMAL",         "reach_restored",   "OR",  _RT_LIFT),
    Transition("CONTENT_FILTER", "NORMAL",         "classifier_clear", "OR",  _CF_LIFT),
    Transition("RATE_LIMIT",     "NORMAL",         "cooldown_elapsed", "OR",  _RL_LIFT),
]


# ── state map for machine initialisation ───────────────────────────────────
# Keyed by underscore-style name used in Transition fields.
_STATE_MAP: dict[str, StateVector] = {
    "NORMAL":         NORMAL,
    "SHADOW_BAN":     SHADOW_BAN.state,
    "CONTENT_FILTER": CONTENT_FILTER.state,
    "RATE_LIMIT":     RATE_LIMIT.state,
    "GEO_BLOCK":      GEO_BLOCK.state,
    "AGE_GATE":       AGE_GATE.state,
    "REACH_THROTTLE": REACH_THROTTLE.state,
}

# index for fast lookup
_FROM_INDEX: dict[str, list[Transition]] = {}
for _t in TRANSITIONS:
    _FROM_INDEX.setdefault(_t.from_state, []).append(_t)


class RestrictionMachine:
    """
    Simulates a node moving through restriction states.

    Each step applies one Transition's bitwise op to the current StateVector.
    The full path is recorded so every bit change is auditable.
    """

    def __init__(self, start: str = "NORMAL"):
        if start not in _STATE_MAP:
            raise KeyError(f"Unknown state {start!r}. Valid: {list(_STATE_MAP)}")
        self.state_name = start
        self.state: StateVector = _STATE_MAP[start]
        self.path: list[tuple[str, str, StateVector]] = [("START", start, self.state)]

    def trigger(self, event: str) -> bool:
        """
        Fire the first matching transition from the current state.
        Returns True if a transition was taken, False if event not recognised.
        """
        for t in _FROM_INDEX.get(self.state_name, []):
            if t.trigger == event:
                new_sv = t.apply(self.state)
                self.path.append((event, t.to_state, new_sv))
                self.state = new_sv
                self.state_name = t.to_state
                return True
        return False

    def available_triggers(self) -> list[str]:
        return [t.trigger for t in _FROM_INDEX.get(self.state_name, [])]

    def trace(self) -> str:
        lines = ["  MACHINE TRACE"]
        lines.append("  " + "─" * 60)
        for event, state_name, sv in self.path:
            lines.append(f"  {event:<24} → {state_name:<18} {sv.to_visual()}")
        lines.append("  " + "─" * 60)
        lines.append(f"  CURRENT  {self.state_name:<18} {self.state.to_visual()}  0b{self.state.to_bits()}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"RestrictionMachine(state={self.state_name!r}, sv={self.state})"


def transition_map() -> str:
    """Pretty-print the full transition table."""
    lines = ["  RESTRICTION STATE MACHINE — TRANSITION TABLE"]
    lines.append("  " + "═" * 68)
    lines.append(f"  {'FROM STATE':<20} {'TRIGGER':<24} {'OP':<4} {'MASK':<10} {'TO STATE'}")
    lines.append("  " + "─" * 68)
    for t in TRANSITIONS:
        lines.append(
            f"  {t.from_state:<20} {t.trigger:<24} {t.op:<4} "
            f"{t.mask.to_visual()}  {t.to_state}"
        )
    lines.append("  " + "─" * 68)
    lines.append(f"  {len(TRANSITIONS)} transitions  |  "
                 f"{len({t.from_state for t in TRANSITIONS})} source states  |  "
                 f"all ops: AND / OR / XOR")
    return "\n".join(lines)
