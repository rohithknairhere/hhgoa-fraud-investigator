from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
DATASET = REPO / "dataset"
STORE = BACKEND / ".store"
CASES_OUT = REPO / "cases"
