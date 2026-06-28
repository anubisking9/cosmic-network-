"""Binary state vectors: every permission lives as a single bit."""

# Bit positions (MSB → LSB, left → right in visual)
READ     = 7
WRITE    = 6
SHARE    = 5
COMMENT  = 4
DISCOVER = 3
NOTIFY   = 2
MONETIZE = 1
LIVE     = 0

PERMISSIONS = [READ, WRITE, SHARE, COMMENT, DISCOVER, NOTIFY, MONETIZE, LIVE]

PERM_NAMES = {
    READ:     "READ    ",
    WRITE:    "WRITE   ",
    SHARE:    "SHARE   ",
    COMMENT:  "COMMENT ",
    DISCOVER: "DISCOVER",
    NOTIFY:   "NOTIFY  ",
    MONETIZE: "MONETIZE",
    LIVE:     "LIVE    ",
}

FULL_ACCESS = 0b11111111


class StateVector:
    """An 8-bit register where each bit is one permission flag."""

    def __init__(self, value: int = FULL_ACCESS):
        self.value = value & 0xFF

    # ── bit access ─────────────────────────────────────────────────────

    def get_bit(self, pos: int) -> int:
        return (self.value >> pos) & 1

    def set_bit(self, pos: int) -> "StateVector":
        return StateVector(self.value | (1 << pos))

    def clear_bit(self, pos: int) -> "StateVector":
        return StateVector(self.value & ~(1 << pos))

    # ── bitwise operations ──────────────────────────────────────────────

    def AND(self, other: "StateVector") -> "StateVector":
        return StateVector(self.value & other.value)

    def OR(self, other: "StateVector") -> "StateVector":
        return StateVector(self.value | other.value)

    def XOR(self, other: "StateVector") -> "StateVector":
        return StateVector(self.value ^ other.value)

    def NOT(self) -> "StateVector":
        return StateVector(~self.value & 0xFF)

    def NAND(self, other: "StateVector") -> "StateVector":
        return self.AND(other).NOT()

    def NOR(self, other: "StateVector") -> "StateVector":
        return self.OR(other).NOT()

    # ── representation ─────────────────────────────────────────────────

    def to_bits(self) -> str:
        return format(self.value, "08b")

    def to_visual(self) -> str:
        """█ for 1 (open), ░ for 0 (blocked)."""
        return "".join("█" if c == "1" else "░" for c in self.to_bits())

    def active_count(self) -> int:
        return bin(self.value).count("1")

    def blocked_count(self) -> int:
        return 8 - self.active_count()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, StateVector) and self.value == other.value

    def __repr__(self) -> str:
        return f"StateVector(0b{self.to_bits()} = {self.value})"
