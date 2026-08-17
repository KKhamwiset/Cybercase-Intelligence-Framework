"""Constants shared by the isolated offline benchmark package."""

DEFAULT_CASE_COUNT = 100
DEFAULT_SEED = 314159
PAIR_COUNT = 8
POSITIVE_PAIR_COUNT = 4
NEGATIVE_PAIR_COUNT = 4
SCHEMA_VERSION = "2.0"

CORRUPTION_TYPES = (
    "actor_swap",
    "target_swap",
    "predicate_swap",
    "timestamp_shift",
    "negation_flip",
    "certainty_strengthening",
    "causality_insertion",
    "attribution_insertion",
)

FORBIDDEN_TERMS = (
    "mitre", "att&ck", "stix", "qdrant", "neo4j", "langgraph", "rag",
    "retrieval", "openrouter", "fastapi", "postgres", "production",
    "backend", "frontend", "llm", "model", "http://", "https://", "database",
)

LEAK_MARKERS = (
    "causal relation inserted", "not established", "confirmed:",
    "attributed to an unlisted observer", "มีการแทรกความเป็นเหตุ",
    "ยังไม่ยืนยัน:", "ยืนยันแล้ว:",
    "ผู้สังเกตการณ์ที่ไม่ได้อยู่ในข้อเท็จจริง",
)

LIMITATIONS = [
    "Cases and labels are synthetic fixtures created from deterministic structured facts.",
    "Construction validation proves agreement with deterministic proposition renderers, not free-form language understanding.",
    "No forensic, deployed-system, or model-quality conclusion can be drawn from this dataset.",
]
