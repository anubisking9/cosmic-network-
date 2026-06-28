"""
Cosmic network graph: nodes with StateVectors connected by permission-matrix edges.
Restrictions propagate along edges via AND; lifts propagate via OR.
"""

from dataclasses import dataclass, field
from .node import CosmicNode
from .state import StateVector, FULL_ACCESS, PERMISSIONS, PERM_NAMES
from .restrictions import Restriction, CONTEXTS


@dataclass
class CosmicEdge:
    source: str
    target: str
    # 8×8 matrix: perm_matrix[perm_row][context_col]  (█=1 / ░=0)
    perm_matrix: list[list[int]] = field(
        default_factory=lambda: [[1] * 8 for _ in range(8)]
    )

    def allows(self, perm_row: int, context_col: int) -> bool:
        return bool(self.perm_matrix[perm_row][context_col])

    def effective_state(self) -> StateVector:
        """Collapse each row to 1 if any context column is open, else 0."""
        bits = 0
        for row_i, pos in enumerate(range(7, -1, -1)):
            if any(self.perm_matrix[row_i]):
                bits |= (1 << pos)
        return StateVector(bits)

    def to_visual(self) -> str:
        perm_labels = ["READ", "WRIT", "SHAR", "CMNT", "DISC", "NTFY", "MONT", "LIVE"]
        lines = [f"  EDGE  {self.source} → {self.target}"]
        lines.append("          " + "  ".join(CONTEXTS))
        for label, row in zip(perm_labels, self.perm_matrix):
            cells = "  ".join("█" if v else "░" for v in row)
            lines.append(f"  {label}    {cells}")
        return "\n".join(lines)


class CosmicGraph:
    """A directed graph of CosmicNodes connected by permission-matrix edges."""

    def __init__(self):
        self.nodes: dict[str, CosmicNode] = {}
        self.edges: list[CosmicEdge] = []

    # ── construction ────────────────────────────────────────────────────

    def add(self, node: CosmicNode) -> "CosmicGraph":
        self.nodes[node.id] = node
        return self

    def connect(
        self,
        source: str,
        target: str,
        perm_matrix: list[list[int]] | None = None,
    ) -> CosmicEdge:
        edge = CosmicEdge(source, target, perm_matrix or [[1] * 8 for _ in range(8)])
        self.edges.append(edge)
        return edge

    # ── restriction propagation ──────────────────────────────────────────

    def propagate(self, r: Restriction, from_id: str) -> list[str]:
        """
        Apply *r* to every node reachable from *from_id* in one hop.
        A zero-effective-state edge blocks the signal entirely.
        Returns IDs of affected nodes.
        """
        affected: list[str] = []
        for edge in self.edges:
            if edge.source != from_id:
                continue
            target = self.nodes.get(edge.target)
            if target is None:
                continue
            edge_sv = edge.effective_state()
            if edge_sv.value == 0:
                continue   # zero-edge: signal does not propagate
            combined = r.state.AND(edge_sv)
            target.force(
                target.state.AND(combined),
                reason=f"PROP {r.code} via {edge.source}",
            )
            affected.append(edge.target)
        return affected

    def lift(self, r: Restriction, from_id: str) -> list[str]:
        """Propagate a restriction lift (OR the trigger_mask) one hop from *from_id*."""
        affected: list[str] = []
        for edge in self.edges:
            if edge.source != from_id:
                continue
            target = self.nodes.get(edge.target)
            if target is None:
                continue
            edge_sv = edge.effective_state()
            if edge_sv.value == 0:
                continue
            # restore only the bits the edge allows through
            restore = r.trigger_mask.AND(edge_sv)
            target.force(
                target.state.OR(restore),
                reason=f"LIFT {r.code} via {edge.source}",
            )
            affected.append(edge.target)
        return affected

    # ── network-level state ──────────────────────────────────────────────

    def consensus(self) -> StateVector:
        """AND of all node states — bits open only where every node allows them."""
        result = StateVector(FULL_ACCESS)
        for node in self.nodes.values():
            result = result.AND(node.state)
        return result

    def union(self) -> StateVector:
        """OR of all node states — bits open if any node allows them."""
        result = StateVector(0)
        for node in self.nodes.values():
            result = result.OR(node.state)
        return result

    # ── visualisation ────────────────────────────────────────────────────

    def state_grid(self) -> str:
        """ASCII grid: one row per node, one column per permission bit."""
        perm_labels = "R W S C D N M L"
        lines = ["  NODE          " + "  ".join(perm_labels.split())]
        lines.append("  " + "─" * 44)
        for nid, node in self.nodes.items():
            bits = "  ".join("█" if node.state.get_bit(p) else "░"
                             for p in range(7, -1, -1))
            lines.append(f"  {nid:<14}{bits}")
        lines.append("  " + "─" * 44)
        con = self.consensus()
        uni = self.union()
        lines.append(f"  {'AND (consensus)':<14}" +
                     "  ".join("█" if con.get_bit(p) else "░" for p in range(7, -1, -1)))
        lines.append(f"  {'OR  (union)':<14}" +
                     "  ".join("█" if uni.get_bit(p) else "░" for p in range(7, -1, -1)))
        return "\n".join(lines)

    def edge_list(self) -> str:
        lines = []
        for e in self.edges:
            eff = e.effective_state()
            lines.append(f"  {e.source} ──→ {e.target}  eff:{eff.to_visual()}")
        return "\n".join(lines) if lines else "  (no edges)"

    def __repr__(self) -> str:
        return f"CosmicGraph(nodes={list(self.nodes)}, edges={len(self.edges)})"
