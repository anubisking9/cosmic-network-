import pytest
from cosmic_network.binary.state import (
    StateVector, FULL_ACCESS,
    READ, WRITE, SHARE, COMMENT, DISCOVER, NOTIFY, MONETIZE, LIVE,
)
from cosmic_network.binary.circuits import Circuit
from cosmic_network.binary.restrictions import (
    RESTRICTIONS, SHADOW_BAN, CONTENT_FILTER, RATE_LIMIT,
    GEO_BLOCK, AGE_GATE, REACH_THROTTLE, FULL,
)


# ── StateVector ────────────────────────────────────────────────────────────

class TestStateVector:
    def test_full_access_visual(self):
        sv = StateVector(FULL_ACCESS)
        assert sv.to_visual() == "████████"

    def test_zero_visual(self):
        sv = StateVector(0)
        assert sv.to_visual() == "░░░░░░░░"

    def test_bit_read(self):
        sv = StateVector(0b10000000)
        assert sv.get_bit(READ) == 1
        assert sv.get_bit(LIVE) == 0

    def test_to_bits_matches_value(self):
        sv = StateVector(0b11010011)
        assert sv.to_bits() == "11010011"

    def test_AND(self):
        a = StateVector(0b11110000)
        b = StateVector(0b10101010)
        assert a.AND(b) == StateVector(0b10100000)

    def test_OR(self):
        a = StateVector(0b11110000)
        b = StateVector(0b00001111)
        assert a.OR(b) == StateVector(0b11111111)

    def test_XOR(self):
        a = StateVector(0b11111111)
        b = StateVector(0b10101010)
        assert a.XOR(b) == StateVector(0b01010101)

    def test_NOT(self):
        sv = StateVector(0b11010011)
        assert sv.NOT() == StateVector(0b00101100)

    def test_NOT_double_inverse(self):
        sv = StateVector(0b11010011)
        assert sv.NOT().NOT() == sv

    def test_active_count(self):
        assert StateVector(0b11010011).active_count() == 5

    def test_blocked_count(self):
        assert StateVector(0b11010011).blocked_count() == 3

    def test_NAND(self):
        a = StateVector(0b11110000)
        b = StateVector(0b10101010)
        assert a.NAND(b) == StateVector(0b11111111) .XOR(StateVector(0b10100000))

    def test_equality(self):
        assert StateVector(42) == StateVector(42)
        assert StateVector(42) != StateVector(43)


# ── Circuit ────────────────────────────────────────────────────────────────

class TestCircuit:
    def test_and_circuit_result(self):
        a = StateVector(0b11110000)
        b = StateVector(0b10101010)
        c = Circuit("test", "AND", a, b)
        assert c.result == StateVector(0b10100000)

    def test_xor_circuit_result(self):
        a = StateVector(0b11111111)
        b = StateVector(0b00100000)   # SHARE delta
        c = Circuit("test", "XOR", a, b)
        assert c.result == StateVector(0b11011111)

    def test_truth_rows_length(self):
        a = StateVector(0b11010011)
        b = StateVector(0b00101100)
        c = Circuit("test", "AND", a, b)
        assert len(c.truth_rows()) == 8

    def test_truth_rows_msb_first(self):
        a = StateVector(0b10000000)   # only bit 7
        b = StateVector(0b11111111)
        c = Circuit("test", "AND", a, b)
        rows = c.truth_rows()
        # first row = bit 7 (MSB)
        assert rows[0] == (1, 1, 1)
        # last row = bit 0 (LSB)
        assert rows[7] == (0, 1, 0)

    def test_not_circuit_no_b(self):
        a = StateVector(0b11010011)
        c = Circuit("not_test", "NOT", a)
        assert c.result == a.NOT()

    def test_invalid_op(self):
        with pytest.raises(ValueError):
            Circuit("bad", "XNOR", StateVector(0b11111111), StateVector(0))

    def test_missing_b_raises(self):
        with pytest.raises(ValueError):
            Circuit("bad", "AND", StateVector(0b11111111))

    def test_gate_symbol(self):
        c = Circuit("t", "XOR", StateVector(0b10101010), StateVector(0b11110000))
        assert c.gate_symbol() == "⊕"


# ── Restrictions ───────────────────────────────────────────────────────────

class TestRestrictions:
    def test_six_restrictions(self):
        assert len(RESTRICTIONS) == 6

    def test_ids_sequential(self):
        for expected, r in enumerate(RESTRICTIONS):
            assert r.id == expected

    def test_shadow_ban_state(self):
        # READ WRITE COMMENT MONETIZE LIVE open; SHARE DISCOVER NOTIFY blocked
        sv = SHADOW_BAN.state
        assert sv.get_bit(READ) == 1
        assert sv.get_bit(WRITE) == 1
        assert sv.get_bit(SHARE) == 0
        assert sv.get_bit(COMMENT) == 1
        assert sv.get_bit(DISCOVER) == 0
        assert sv.get_bit(NOTIFY) == 0

    def test_geo_block_zero(self):
        assert GEO_BLOCK.state.value == 0
        assert GEO_BLOCK.state.to_visual() == "░░░░░░░░"

    def test_geo_block_matrix_all_zeros(self):
        for row in GEO_BLOCK.perm_matrix:
            assert all(v == 0 for v in row)

    def test_age_gate_only_read_discover(self):
        sv = AGE_GATE.state
        assert sv.get_bit(READ) == 1
        assert sv.get_bit(DISCOVER) == 1
        assert sv.get_bit(WRITE) == 0
        assert sv.get_bit(LIVE) == 0

    def test_rate_limit_only_live_blocked(self):
        sv = RATE_LIMIT.state
        assert sv.get_bit(LIVE) == 0
        assert sv.active_count() == 7

    def test_reach_throttle_only_discover_blocked(self):
        sv = REACH_THROTTLE.state
        assert sv.get_bit(DISCOVER) == 0
        assert sv.active_count() == 7

    def test_content_filter_only_share_blocked(self):
        sv = CONTENT_FILTER.state
        assert sv.get_bit(SHARE) == 0
        assert sv.active_count() == 7

    def test_signature_is_16_bits(self):
        for r in RESTRICTIONS:
            assert len(r.signature) == 16
            assert all(b in (0, 1) for b in r.signature)

    def test_signature_second_half_is_complement(self):
        for r in RESTRICTIONS:
            first = r.signature[:8]
            second = r.signature[8:]
            assert all(a + b == 1 for a, b in zip(first, second))

    def test_perm_matrix_shape(self):
        for r in RESTRICTIONS:
            assert len(r.perm_matrix) == 8
            for row in r.perm_matrix:
                assert len(row) == 8

    def test_blocked_perms_have_zero_matrix_row(self):
        """Every permission blocked in the state vector must have an all-zero row."""
        perm_order = [READ, WRITE, SHARE, COMMENT, DISCOVER, NOTIFY, MONETIZE, LIVE]
        for r in RESTRICTIONS:
            for row_i, pos in enumerate(range(7, -1, -1)):
                if r.state.get_bit(pos) == 0:
                    assert all(v == 0 for v in r.perm_matrix[row_i]), (
                        f"{r.name}: perm b{pos} blocked in state "
                        f"but matrix row {row_i} has 1s: {r.perm_matrix[row_i]}"
                    )

    def test_trigger_mask_is_complement_of_open_bits(self):
        """Trigger mask should cover only the bits that are 0 in state."""
        for r in RESTRICTIONS:
            for pos in range(8):
                state_bit = r.state.get_bit(pos)
                trigger_bit = r.trigger_mask.get_bit(pos)
                if state_bit == 1:
                    assert trigger_bit == 0, (
                        f"{r.name}: bit {pos} is open in state but set in trigger"
                    )

    def test_circuit_result_matches_state(self):
        """The circuit must produce the restriction's state vector."""
        for r in RESTRICTIONS:
            c = Circuit(r.name, r.circuit_op, FULL, r.circuit_b)
            assert c.result == r.state, (
                f"{r.name}: circuit result {c.result} ≠ state {r.state}"
            )

    def test_full_and_with_zero_gives_zero(self):
        assert FULL.AND(StateVector(0)) == StateVector(0)

    def test_full_xor_delta_gives_state(self):
        for r in [CONTENT_FILTER, REACH_THROTTLE]:
            c = Circuit(r.name, r.circuit_op, FULL, r.circuit_b)
            assert c.result == r.state
