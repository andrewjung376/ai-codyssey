import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402
from routers.chat import llm_dependency  # noqa: E402
from services.repository import MemoryRepository, get_repository  # noqa: E402


class FakeLLM:
    """OpenAI 대신 호출 내용을 기록하고 고정 답변을 돌려준다."""

    def __init__(self):
        self.calls: list[list[dict]] = []

    def complete(self, messages):
        self.calls.append(messages)
        return f"답변 #{len(self.calls)}"


@pytest.fixture
def repo():
    r = MemoryRepository()
    r.bulk_insert_data([
        {"date": f"2026-01-{day:02d}", "value": 100.0 + day, "memo": ""} for day in range(1, 26)
    ])
    return r


@pytest.fixture
def llm():
    return FakeLLM()


@pytest.fixture
def client(repo, llm):
    app.dependency_overrides[get_repository] = lambda: repo
    app.dependency_overrides[llm_dependency] = lambda: llm
    yield TestClient(app)
    app.dependency_overrides.clear()
