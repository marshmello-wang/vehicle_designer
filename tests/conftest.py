import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest
import warnings


# Ensure project root is on sys.path for `from app...` imports
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ---- Fake Supabase client for tests (in-memory) ----


@dataclass
class _Resp:
    data: Optional[List[Dict[str, Any]]] = None
    count: Optional[int] = None


class _Query:
    def __init__(self, table: "_Table"):
        self._table = table
        self._filters: List = []
        self._order_key: Optional[str] = None
        self._order_desc: bool = False
        self._limit: Optional[int] = None
        self._count_mode: Optional[str] = None
        self._select_cols: Optional[str] = None

    def select(self, cols: str, **kwargs):
        self._select_cols = cols
        self._count_mode = kwargs.get("count")
        return self

    def eq(self, key: str, value: Any):
        self._filters.append((key, value))
        return self

    def order(self, key: str, desc: bool = False):
        self._order_key = key
        self._order_desc = bool(desc)
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def execute(self) -> _Resp:
        rows = list(self._table._rows)
        for k, v in self._filters:
            rows = [r for r in rows if r.get(k) == v]
        if self._order_key:
            rows.sort(key=lambda r: r.get(self._order_key), reverse=self._order_desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        # apply projection if simple list of columns
        if self._select_cols and self._select_cols.strip() != "*":
            cols = [c.strip() for c in self._select_cols.split(",")]
            proj = []
            for r in rows:
                proj.append({k: r.get(k) for k in cols})
            rows = proj
        cnt = len(rows) if self._count_mode == "exact" else None
        return _Resp(data=rows, count=cnt)


class _Table:
    def __init__(self, name: str, storage: Dict[str, List[Dict[str, Any]]]):
        self._name = name
        self._storage = storage
        self._rows = storage.setdefault(name, [])
        self._pending_insert: Optional[List[Dict[str, Any]]] = None

    def insert(self, row: Dict[str, Any]):
        # supabase-py supports list insertion as well; handle dict case for tests
        self._pending_insert = [row]
        return self

    def execute(self) -> _Resp:
        if self._pending_insert is not None:
            self._rows.extend(self._pending_insert)
            out = _Resp(data=self._pending_insert)
            self._pending_insert = None
            return out
        return _Resp(data=[])

    # query builder
    def select(self, cols: str, **kwargs) -> _Query:
        return _Query(self).select(cols, **kwargs)

    def eq(self, key: str, value: Any) -> _Query:
        return _Query(self).eq(key, value)

    def order(self, key: str, desc: bool = False) -> _Query:
        return _Query(self).order(key, desc)

    def limit(self, n: int) -> _Query:
        return _Query(self).limit(n)


class _FakeClient:
    def __init__(self):
        self._storage: Dict[str, List[Dict[str, Any]]] = {}

    def table(self, name: str) -> _Table:
        return _Table(name, self._storage)


@pytest.fixture(autouse=True)
def _supabase_mode(monkeypatch):
    """By default, tests use an in-memory fake Supabase.

    To run tests against a real Supabase project, export SUPABASE_TEST_REAL=true
    and ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set.
    """
    # Always fake Ark in tests
    os.environ.setdefault("ARK_FAKE_MODE", "true")

    use_real = os.getenv("SUPABASE_TEST_REAL", "false").lower() in {"1", "true", "yes"}
    if not use_real:
        import app.db as adb

        fake = _FakeClient()
        monkeypatch.setattr(adb, "get_client", lambda: fake, raising=True)
        monkeypatch.setattr(adb, "_require_env", lambda: None, raising=True)

    yield
# Silence deprecations from third-party client versions during tests
# Suppress deprecation warnings coming from third-party libs during tests
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"supabase\..*")
warnings.filterwarnings("ignore", category=DeprecationWarning)
