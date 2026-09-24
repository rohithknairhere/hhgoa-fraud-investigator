import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data.scenarios import SCENARIOS, build_dataset  # noqa: E402
from app.graph.mock_provider import MockGraphProvider  # noqa: E402


@pytest.fixture
def provider() -> MockGraphProvider:
    build_dataset()
    return MockGraphProvider()


@pytest.fixture
def scenarios():
    build_dataset()
    return {s.case_id: s for s in SCENARIOS}
