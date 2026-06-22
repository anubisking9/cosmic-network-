"""
A cosmic network node: an entity whose entire capability set lives in one
StateVector.  All restrictions are applied and lifted through bitwise ops.
"""

from .state import StateVector, FULL_ACCESS, PERMISSIONS, PERM_NAMES
from .restrictions import Restriction, FULL


class CosmicNode:
    def __init__(self, node_id: str, state: StateVector | None = None):
        self.id = node_id
        self.state: StateVector = state or StateVector(FULL_ACCESS)
        # log of (reason, state_before) so every change is traceable
        self._log: list[tuple[str, StateVector]] = []

    # ── apply / lift ────────────────────────────────────────────────────

    def apply(self, r: Restriction) -> "CosmicNode":
        """AND the node's state with the restriction mask (clears blocked bits)."""
        self._log.append((f"APPLY {r.code}", self.state))
        self.state = self.state.AND(r.state)
        return self

    def lift(self, r: Restriction) -> "CosmicNode":
        """OR the node's state with the restriction's trigger_mask (restores blocked bits)."""
        self._log.append((f"LIFT  {r.code}", self.state))
        self.state = self.state.OR(r.trigger_mask)
        return self

    def force(self, new_state: StateVector, reason: str = "FORCE") -> "CosmicNode":
        """Unconditionally write a new state (used by state machine transitions)."""
        self._log.append((reason, self.state))
        self.state = new_state
        return self

    # ── permission queries ──────────────────────────────────────────────

    def can(self, perm: int) -> bool:
        return bool(self.state.get_bit(perm))

    def blocked_perms(self) -> list[int]:
        return [p for p in PERMISSIONS if not self.can(p)]

    def open_perms(self) -> list[int]:
        return [p for p in PERMISSIONS if self.can(p)]

    # ── display ─────────────────────────────────────────────────────────

    def status_line(self) -> str:
        return f"{self.id:<12}  {self.state.to_visual()}  0b{self.state.to_bits()}  ({self.state.value:3d})"

    def full_report(self) -> str:
        lines = [f"NODE  {self.id}", f"  STATE  {self.state.to_visual()}  0b{self.state.to_bits()}"]
        for perm in range(7, -1, -1):
            v = "█  OPEN   " if self.state.get_bit(perm) else "░  BLOCKED"
            lines.append(f"  b{perm}  {PERM_NAMES[perm]}  {v}")
        if self._log:
            lines.append("  HISTORY")
            for reason, before in self._log[-4:]:
                lines.append(f"    {reason:<20}  {before.to_visual()} → {self.state.to_visual()}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"CosmicNode({self.id!r}, {self.state})"
