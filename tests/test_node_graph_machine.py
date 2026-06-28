import pytest
from cosmic_network.binary.state import StateVector, FULL_ACCESS, READ, WRITE, SHARE, DISCOVER
from cosmic_network.binary.restrictions import (
    SHADOW_BAN, CONTENT_FILTER, RATE_LIMIT, GEO_BLOCK, AGE_GATE, REACH_THROTTLE, FULL,
)
from cosmic_network.binary.node import CosmicNode
from cosmic_network.binary.graph import CosmicGraph, CosmicEdge
from cosmic_network.binary.machine import RestrictionMachine, TRANSITIONS, NORMAL, transition_map


# ── CosmicNode ─────────────────────────────────────────────────────────────

class TestCosmicNode:
    def test_default_full_access(self):
        n = CosmicNode("alice")
        assert n.state == StateVector(FULL_ACCESS)

    def test_can_all_perms_by_default(self):
        n = CosmicNode("alice")
        for p in range(8):
            assert n.can(p)

    def test_apply_geo_block_zeros_everything(self):
        n = CosmicNode("alice")
        n.apply(GEO_BLOCK)
        assert n.state.value == 0
        assert not n.can(READ)

    def test_apply_shadow_ban_blocks_discover(self):
        n = CosmicNode("alice")
        n.apply(SHADOW_BAN)
        assert not n.can(DISCOVER)
        assert not n.can(SHARE)
        assert n.can(READ)
        assert n.can(WRITE)

    def test_apply_then_lift_restores_bits(self):
        n = CosmicNode("alice")
        n.apply(RATE_LIMIT)          # blocks LIVE
        n.lift(RATE_LIMIT)           # restores LIVE
        assert n.state == StateVector(FULL_ACCESS)

    def test_history_recorded(self):
        n = CosmicNode("bob")
        n.apply(SHADOW_BAN)
        n.apply(RATE_LIMIT)
        assert len(n._log) == 2
        assert n._log[0][0] == "APPLY SB-01"
        assert n._log[1][0] == "APPLY RL-03"

    def test_force_sets_exact_state(self):
        n = CosmicNode("carol")
        target = StateVector(0b10101010)
        n.force(target, "test")
        assert n.state == target

    def test_blocked_perms_list(self):
        n = CosmicNode("dave")
        n.apply(AGE_GATE)
        blocked = n.blocked_perms()
        # AGE_GATE opens READ(7) and DISCOVER(3) only — 6 blocked
        assert len(blocked) == 6
        assert WRITE in blocked
        assert SHARE in blocked

    def test_open_perms_list(self):
        n = CosmicNode("eve")
        n.apply(AGE_GATE)
        open_p = n.open_perms()
        assert open_p == [READ, DISCOVER]

    def test_status_line_contains_visual(self):
        n = CosmicNode("frank")
        n.apply(GEO_BLOCK)
        line = n.status_line()
        assert "░░░░░░░░" in line
        assert "frank" in line

    def test_stacking_restrictions_narrows(self):
        n = CosmicNode("grace")
        n.apply(CONTENT_FILTER)   # blocks SHARE
        n.apply(RATE_LIMIT)       # additionally blocks LIVE
        assert not n.can(SHARE)
        assert not n.can(0)       # LIVE = bit 0

    def test_custom_initial_state(self):
        sv = StateVector(0b11001100)
        n = CosmicNode("heidi", sv)
        assert n.state == sv


# ── CosmicGraph ────────────────────────────────────────────────────────────

class TestCosmicGraph:
    def _two_node_graph(self):
        g = CosmicGraph()
        g.add(CosmicNode("src"))
        g.add(CosmicNode("dst"))
        g.connect("src", "dst")
        return g

    def test_add_node(self):
        g = CosmicGraph()
        n = CosmicNode("x")
        g.add(n)
        assert "x" in g.nodes

    def test_connect_creates_edge(self):
        g = self._two_node_graph()
        assert len(g.edges) == 1
        assert g.edges[0].source == "src"
        assert g.edges[0].target == "dst"

    def test_propagate_restriction_to_target(self):
        g = self._two_node_graph()
        g.nodes["src"].apply(SHADOW_BAN)
        affected = g.propagate(SHADOW_BAN, "src")
        assert "dst" in affected
        assert not g.nodes["dst"].can(DISCOVER)

    def test_propagate_returns_affected_ids(self):
        g = CosmicGraph()
        for nid in ("a", "b", "c"):
            g.add(CosmicNode(nid))
        g.connect("a", "b")
        g.connect("a", "c")
        affected = g.propagate(GEO_BLOCK, "a")
        assert set(affected) == {"b", "c"}

    def test_blocked_edge_stops_propagation(self):
        g = CosmicGraph()
        g.add(CosmicNode("src"))
        g.add(CosmicNode("dst"))
        # edge with all zeros — nothing passes
        zero_matrix = [[0] * 8 for _ in range(8)]
        g.connect("src", "dst", zero_matrix)
        g.propagate(CONTENT_FILTER, "src")
        # dst should still be at full access because edge blocked everything
        assert g.nodes["dst"].state == StateVector(FULL_ACCESS)

    def test_partial_edge_passes_open_bits_only(self):
        g = CosmicGraph()
        g.add(CosmicNode("src"))
        g.add(CosmicNode("dst"))
        # edge blocks SHARE row (row 2)
        partial = [[1] * 8 for _ in range(8)]
        partial[2] = [0] * 8
        g.connect("src", "dst", partial)
        g.propagate(REACH_THROTTLE, "src")
        # REACH_THROTTLE blocks DISCOVER(3); partial edge also blocks SHARE(5)
        assert not g.nodes["dst"].can(DISCOVER)

    def test_consensus_all_full(self):
        g = CosmicGraph()
        for nid in ("a", "b", "c"):
            g.add(CosmicNode(nid))
        assert g.consensus() == StateVector(FULL_ACCESS)

    def test_consensus_reflects_blocked_bit(self):
        g = CosmicGraph()
        g.add(CosmicNode("a"))
        g.add(CosmicNode("b"))
        g.nodes["a"].apply(GEO_BLOCK)
        # AND of full (b) and zero (a) = zero
        assert g.consensus().value == 0

    def test_union_reflects_any_open(self):
        g = CosmicGraph()
        g.add(CosmicNode("a"))
        g.add(CosmicNode("b"))
        g.nodes["a"].apply(GEO_BLOCK)   # a = 0x00
        # OR of 0x00 and 0xFF = 0xFF
        assert g.union() == StateVector(FULL_ACCESS)

    def test_effective_state_full_edge(self):
        e = CosmicEdge("x", "y")   # default: all 1s
        assert e.effective_state() == StateVector(FULL_ACCESS)

    def test_effective_state_zero_edge(self):
        e = CosmicEdge("x", "y", [[0] * 8 for _ in range(8)])
        assert e.effective_state().value == 0

    def test_state_grid_contains_node_ids(self):
        g = CosmicGraph()
        g.add(CosmicNode("alpha"))
        g.add(CosmicNode("beta"))
        grid = g.state_grid()
        assert "alpha" in grid
        assert "beta" in grid

    def test_lift_propagation(self):
        g = self._two_node_graph()
        g.nodes["src"].apply(RATE_LIMIT)
        g.nodes["dst"].apply(RATE_LIMIT)
        g.lift(RATE_LIMIT, "src")
        # dst should have LIVE restored via OR propagation
        assert g.nodes["dst"].can(0)   # LIVE = bit 0


# ── RestrictionMachine ─────────────────────────────────────────────────────

class TestRestrictionMachine:
    def test_initial_state_normal(self):
        m = RestrictionMachine()
        assert m.state_name == "NORMAL"
        assert m.state == NORMAL

    def test_trigger_rate_limit(self):
        m = RestrictionMachine()
        ok = m.trigger("bucket_overflow")
        assert ok
        assert m.state_name == "RATE_LIMIT"
        assert m.state == RATE_LIMIT.state

    def test_trigger_unknown_returns_false(self):
        m = RestrictionMachine()
        assert not m.trigger("nonexistent_event")
        assert m.state_name == "NORMAL"

    def test_chain_normal_to_shadow_ban(self):
        m = RestrictionMachine()
        m.trigger("bucket_overflow")       # NORMAL → RATE_LIMIT
        m.trigger("limit_persists")        # RATE_LIMIT → SHADOW_BAN
        assert m.state_name == "SHADOW_BAN"
        assert m.state == SHADOW_BAN.state

    def test_partial_lift_shadow_to_throttle(self):
        m = RestrictionMachine()
        m.trigger("bucket_overflow")
        m.trigger("limit_persists")
        m.trigger("appeal_partial")        # SHADOW_BAN → REACH_THROTTLE
        assert m.state_name == "REACH_THROTTLE"
        assert m.state == REACH_THROTTLE.state

    def test_age_gate_full_cycle(self):
        m = RestrictionMachine("AGE_GATE")
        assert m.state == AGE_GATE.state
        m.trigger("kyc_cleared")
        assert m.state_name == "NORMAL"
        assert m.state == NORMAL

    def test_reach_throttle_restore(self):
        m = RestrictionMachine("REACH_THROTTLE")
        assert m.state == REACH_THROTTLE.state
        m.trigger("reach_restored")
        assert m.state_name == "NORMAL"
        assert m.state == NORMAL

    def test_geo_block_is_terminal(self):
        m = RestrictionMachine()
        m.trigger("geo_match")
        assert m.state_name == "GEO_BLOCK"
        assert m.state.value == 0
        # no transitions out of GEO_BLOCK defined
        assert m.available_triggers() == []

    def test_path_recorded(self):
        m = RestrictionMachine()
        m.trigger("bucket_overflow")
        m.trigger("limit_persists")
        # path: START, bucket_overflow, limit_persists = 3 entries
        assert len(m.path) == 3

    def test_available_triggers_from_normal(self):
        m = RestrictionMachine()
        triggers = m.available_triggers()
        assert "bucket_overflow" in triggers
        assert "classifier_trip" in triggers
        assert "kyc_missing" in triggers
        assert "geo_match" in triggers

    def test_all_transitions_produce_correct_state(self):
        from cosmic_network.binary.machine import _STATE_MAP
        for t in TRANSITIONS:
            from_sv = _STATE_MAP.get(t.from_state)
            to_sv = _STATE_MAP.get(t.to_state)
            if from_sv is None or to_sv is None:
                continue
            result = t.apply(from_sv)
            assert result == to_sv, (
                f"Transition {t.from_state}→{t.to_state} via {t.trigger}: "
                f"got {result}, expected {to_sv}"
            )

    def test_transition_map_string(self):
        s = transition_map()
        assert "SHADOW_BAN" in s
        assert "GEO_BLOCK" in s
        assert "AND" in s
        assert "XOR" in s

    def test_trace_contains_all_states(self):
        m = RestrictionMachine()
        m.trigger("bucket_overflow")
        m.trigger("limit_persists")
        trace = m.trace()
        assert "NORMAL" in trace
        assert "RATE_LIMIT" in trace
        assert "SHADOW_BAN" in trace
