"""
The 6 major cosmic-network restrictions.

Each restriction is fully expressed as binary:
  - state vector   : which permission bits survive
  - trigger mask   : which blocked bits define this restriction
  - binary signature: 16-bit fingerprint (state ++ NOT(state))
  - permission matrix: 8 permissions × 8 contexts
  - logic circuit  : the primary gate operation that implements the mask
"""

from dataclasses import dataclass
from .state import StateVector, FULL_ACCESS
from .circuits import Circuit

FULL = StateVector(FULL_ACCESS)

# Context columns for the permission matrix
CONTEXTS = ["OWN ", "FLWR", "PUB ", "SRCH", "EXT ", "API ", "MOD ", "BOT "]


@dataclass
class Restriction:
    id: int
    name: str
    code: str
    description: str
    state: StateVector
    trigger_mask: StateVector
    signature: list[int]           # 16-bit list of 0/1
    perm_matrix: list[list[int]]   # 8 perms × 8 contexts
    circuit_op: str
    circuit_b: StateVector


def _sig(sv: StateVector) -> list[int]:
    """16-bit signature: state bits concatenated with their complement."""
    bits = [int(c) for c in sv.to_bits()]
    complement = [1 - b for b in bits]
    return bits + complement


# ── 1. SHADOW BAN ──────────────────────────────────────────────────────────
#   state   = 0b11010011  ██░█░░██
#   blocked = SHARE(5)  DISCOVER(3)  NOTIFY(2)
#   circuit = FULL AND state
_SB_STATE   = StateVector(0b11010011)   # READ WRITE COMMENT MONETIZE LIVE
_SB_TRIGGER = StateVector(0b00101100)   # SHARE DISCOVER NOTIFY blocked

SHADOW_BAN = Restriction(
    id=0,
    name="SHADOW BAN",
    code="SB-01",
    description=(
        "Account appears active. Write ops complete without error.\n"
        "Output excluded from discovery graph and peer feeds.\n"
        "Self-read returns 1. Follower-read returns 0."
    ),
    state=_SB_STATE,
    trigger_mask=_SB_TRIGGER,
    signature=_sig(_SB_STATE),
    circuit_op="AND",
    circuit_b=_SB_STATE,
    perm_matrix=[
        # OWN FLWR PUB SRCH EXT  API  MOD  BOT
        [1,   1,   0,   0,   0,   1,   1,   1],   # READ
        [1,   1,   1,   1,   1,   1,   1,   1],   # WRITE  (proceeds; invisible)
        [0,   0,   0,   0,   0,   0,   0,   0],   # SHARE  blocked
        [1,   0,   0,   0,   0,   0,   1,   0],   # COMMENT (self+mod only)
        [0,   0,   0,   0,   0,   0,   0,   0],   # DISCOVER blocked
        [0,   0,   0,   0,   0,   0,   0,   0],   # NOTIFY  blocked
        [1,   0,   0,   0,   0,   0,   0,   0],   # MONETIZE (own session only)
        [1,   1,   0,   0,   0,   0,   0,   1],   # LIVE (self+follower; bot analytics)
    ],
)

# ── 2. CONTENT FILTER ──────────────────────────────────────────────────────
#   state   = 0b11011111  ██░█████
#   blocked = SHARE(5)
#   circuit = FULL XOR delta   (delta = 0b00100000, exactly the SHARE bit)
_CF_STATE   = StateVector(0b11011111)
_CF_DELTA   = FULL.XOR(_CF_STATE)           # 0b00100000
_CF_TRIGGER = StateVector(0b00100000)

CONTENT_FILTER = Restriction(
    id=1,
    name="CONTENT FILTER",
    code="CF-02",
    description=(
        "Classifier intercepts content before broadcast.\n"
        "WRITE proceeds; flagged SHARE bit is zeroed at egress.\n"
        "XOR delta isolates the exact suppressed bit."
    ),
    state=_CF_STATE,
    trigger_mask=_CF_TRIGGER,
    signature=_sig(_CF_STATE),
    circuit_op="XOR",
    circuit_b=_CF_DELTA,
    perm_matrix=[
        # OWN FLWR PUB SRCH EXT  API  MOD  BOT
        [1,   1,   1,   1,   1,   1,   1,   1],   # READ
        [1,   1,   1,   1,   1,   1,   1,   1],   # WRITE
        [0,   0,   0,   0,   0,   0,   0,   0],   # SHARE  blocked
        [1,   1,   1,   0,   0,   1,   1,   1],   # COMMENT
        [1,   1,   0,   0,   1,   1,   1,   1],   # DISCOVER (not in pub/srch)
        [1,   1,   1,   0,   0,   1,   1,   1],   # NOTIFY
        [1,   0,   0,   0,   0,   0,   1,   0],   # MONETIZE (own+mod)
        [1,   1,   1,   0,   0,   1,   1,   1],   # LIVE
    ],
)

# ── 3. RATE LIMIT ──────────────────────────────────────────────────────────
#   state   = 0b11111110  ███████░
#   blocked = LIVE(0)  (streaming gated; counter saturates bucket)
#   circuit = FULL AND state
_RL_STATE   = StateVector(0b11111110)
_RL_TRIGGER = StateVector(0b00000001)

RATE_LIMIT = Restriction(
    id=2,
    name="RATE LIMIT",
    code="RL-03",
    description=(
        "Token bucket saturated. Action counter overflowed threshold.\n"
        "LIVE bit trips the circuit breaker; streaming gated.\n"
        "Bit rotates back in after cooldown window resets register."
    ),
    state=_RL_STATE,
    trigger_mask=_RL_TRIGGER,
    signature=_sig(_RL_STATE),
    circuit_op="AND",
    circuit_b=_RL_STATE,
    perm_matrix=[
        # OWN FLWR PUB SRCH EXT  API  MOD  BOT
        [1,   1,   1,   1,   1,   1,   1,   1],   # READ
        [1,   1,   1,   1,   0,   1,   1,   0],   # WRITE  (rate-gated for ext/bot)
        [1,   1,   1,   0,   0,   0,   1,   0],   # SHARE
        [1,   1,   1,   1,   0,   1,   1,   0],   # COMMENT
        [1,   1,   1,   1,   1,   1,   1,   1],   # DISCOVER
        [1,   1,   1,   1,   0,   1,   1,   0],   # NOTIFY
        [1,   1,   0,   0,   0,   0,   1,   0],   # MONETIZE
        [0,   0,   0,   0,   0,   0,   0,   0],   # LIVE    blocked
    ],
)

# ── 4. GEO BLOCK ───────────────────────────────────────────────────────────
#   state   = 0b00000000  ░░░░░░░░
#   blocked = all 8 bits
#   circuit = FULL AND 0x00   (null mask zeros everything)
_GB_STATE   = StateVector(0b00000000)
_GB_TRIGGER = StateVector(0b11111111)

GEO_BLOCK = Restriction(
    id=3,
    name="GEO BLOCK",
    code="GB-04",
    description=(
        "Regional routing table drops all egress packets.\n"
        "AND mask = 0x00 — no bit survives the gate.\n"
        "Full blackout. All 8 permission lines open-circuit."
    ),
    state=_GB_STATE,
    trigger_mask=_GB_TRIGGER,
    signature=_sig(_GB_STATE),
    circuit_op="AND",
    circuit_b=_GB_STATE,
    perm_matrix=[
        # OWN FLWR PUB SRCH EXT  API  MOD  BOT
        [0,   0,   0,   0,   0,   0,   0,   0],   # READ
        [0,   0,   0,   0,   0,   0,   0,   0],   # WRITE
        [0,   0,   0,   0,   0,   0,   0,   0],   # SHARE
        [0,   0,   0,   0,   0,   0,   0,   0],   # COMMENT
        [0,   0,   0,   0,   0,   0,   0,   0],   # DISCOVER
        [0,   0,   0,   0,   0,   0,   0,   0],   # NOTIFY
        [0,   0,   0,   0,   0,   0,   0,   0],   # MONETIZE
        [0,   0,   0,   0,   0,   0,   0,   0],   # LIVE
    ],
)

# ── 5. AGE GATE ────────────────────────────────────────────────────────────
#   state   = 0b10001000  █░░░█░░░
#   open    = READ(7)  DISCOVER(3)  — minimum browse permissions
#   blocked = WRITE SHARE COMMENT NOTIFY MONETIZE LIVE
#   circuit = FULL AND state
_AG_STATE   = StateVector(0b10001000)
_AG_TRIGGER = StateVector(0b01110111)   # everything except READ+DISCOVER

AGE_GATE = Restriction(
    id=4,
    name="AGE GATE",
    code="AG-05",
    description=(
        "Verification bit unset. KYC incomplete; restricted mode active.\n"
        "READ + DISCOVER held open for onboarding flow.\n"
        "All other permission bits locked to 0 until identity clears."
    ),
    state=_AG_STATE,
    trigger_mask=_AG_TRIGGER,
    signature=_sig(_AG_STATE),
    circuit_op="AND",
    circuit_b=_AG_STATE,
    perm_matrix=[
        # OWN FLWR PUB SRCH EXT  API  MOD  BOT
        [1,   0,   0,   1,   0,   0,   1,   1],   # READ     (own+srch+mod+bot)
        [0,   0,   0,   0,   0,   0,   0,   0],   # WRITE    blocked
        [0,   0,   0,   0,   0,   0,   0,   0],   # SHARE    blocked
        [0,   0,   0,   0,   0,   0,   0,   0],   # COMMENT  blocked
        [1,   0,   0,   1,   0,   0,   1,   1],   # DISCOVER (own+srch+mod+bot)
        [0,   0,   0,   0,   0,   0,   0,   0],   # NOTIFY   blocked
        [0,   0,   0,   0,   0,   0,   0,   0],   # MONETIZE blocked
        [0,   0,   0,   0,   0,   0,   0,   0],   # LIVE     blocked
    ],
)

# ── 6. REACH THROTTLE ──────────────────────────────────────────────────────
#   state   = 0b11110111  ████░███
#   blocked = DISCOVER(3)  — algo multiplier clamped to ≈ 0
#   circuit = FULL XOR delta   (delta = 0b00001000, exactly the DISCOVER bit)
_RT_STATE   = StateVector(0b11110111)
_RT_DELTA   = FULL.XOR(_RT_STATE)           # 0b00001000
_RT_TRIGGER = StateVector(0b00001000)

REACH_THROTTLE = Restriction(
    id=5,
    name="REACH THROTTLE",
    code="RT-06",
    description=(
        "Algo rank multiplier clamped to near-zero float.\n"
        "Content exists in graph; all bits structurally intact.\n"
        "DISCOVER bit XOR-masked out; distribution probability → 0."
    ),
    state=_RT_STATE,
    trigger_mask=_RT_TRIGGER,
    signature=_sig(_RT_STATE),
    circuit_op="XOR",
    circuit_b=_RT_DELTA,
    perm_matrix=[
        # OWN FLWR PUB SRCH EXT  API  MOD  BOT
        [1,   1,   1,   1,   1,   1,   1,   1],   # READ
        [1,   1,   1,   1,   1,   1,   1,   1],   # WRITE
        [1,   1,   0,   0,   0,   1,   1,   0],   # SHARE  (limited reach)
        [1,   1,   1,   1,   0,   1,   1,   1],   # COMMENT
        [0,   0,   0,   0,   0,   0,   0,   0],   # DISCOVER blocked (throttle)
        [1,   1,   0,   0,   0,   1,   1,   0],   # NOTIFY  throttled
        [1,   1,   0,   0,   0,   0,   1,   0],   # MONETIZE throttled
        [1,   1,   1,   0,   0,   1,   1,   1],   # LIVE
    ],
)

RESTRICTIONS = [
    SHADOW_BAN,
    CONTENT_FILTER,
    RATE_LIMIT,
    GEO_BLOCK,
    AGE_GATE,
    REACH_THROTTLE,
]
