"""Bitwise logic circuits: AND / OR / XOR / NOT evaluated bit-by-bit."""

from .state import StateVector


OPS = ("AND", "OR", "XOR", "NOT", "NAND", "NOR")


class Circuit:
    """
    A named two-input (or one-input for NOT) bitwise gate array.

    Each of the 8 permission bits passes through the same gate in parallel,
    modelling the restriction logic as a hardware truth-table column.
    """

    def __init__(self, name: str, op: str, a: StateVector, b: StateVector | None = None):
        if op not in OPS:
            raise ValueError(f"op must be one of {OPS}")
        if op != "NOT" and b is None:
            raise ValueError(f"op {op!r} requires a second operand")

        self.name = name
        self.op = op
        self.a = a
        self.b = b

        if op == "AND":
            self.result = a.AND(b)
        elif op == "OR":
            self.result = a.OR(b)
        elif op == "XOR":
            self.result = a.XOR(b)
        elif op == "NOT":
            self.result = a.NOT()
        elif op == "NAND":
            self.result = a.NAND(b)
        elif op == "NOR":
            self.result = a.NOR(b)

    def truth_rows(self) -> list[tuple[int, int | None, int]]:
        """(in_a, in_b, out) for each bit from MSB (pos 7) to LSB (pos 0)."""
        rows = []
        for pos in range(7, -1, -1):
            a_bit = self.a.get_bit(pos)
            b_bit = self.b.get_bit(pos) if self.b is not None else None
            r_bit = self.result.get_bit(pos)
            rows.append((a_bit, b_bit, r_bit))
        return rows

    def gate_symbol(self) -> str:
        return {
            "AND": "∧", "OR": "∨", "XOR": "⊕",
            "NOT": "¬", "NAND": "⊼", "NOR": "⊽",
        }[self.op]
