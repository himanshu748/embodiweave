"""FalkorDB connection. Reads go through GRAPH.RO_QUERY; writes only through trusted ingest code."""
from __future__ import annotations

import os
import time

from falkordb import FalkorDB

GRAPH = os.environ.get("EW_GRAPH", "ew")
HOST = os.environ.get("EW_FALKOR_HOST", "localhost")
PORT = int(os.environ.get("EW_FALKOR_PORT", "6379"))


class GraphUnavailable(RuntimeError):
    """Raised when FalkorDB cannot be reached. Graph-dependent decisions must stop."""


_db = None


def _conn():
    global _db
    if _db is None:
        _db = FalkorDB(host=HOST, port=PORT, socket_timeout=3, socket_connect_timeout=2)
    return _db


def graph(name: str | None = None):
    return _conn().select_graph(name or GRAPH)


def _wrap(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (ConnectionError, TimeoutError, OSError) as e:
        raise GraphUnavailable(f"FalkorDB unreachable at {HOST}:{PORT}: {e.__class__.__name__}") from e
    except Exception as e:  # redis.exceptions.ConnectionError subclasses
        if "Connection" in e.__class__.__name__ or "Timeout" in e.__class__.__name__:
            raise GraphUnavailable(f"FalkorDB unreachable at {HOST}:{PORT}: {e.__class__.__name__}") from e
        raise


def ro(query: str, params: dict | None = None, graph_name: str | None = None):
    """Read-only query (GRAPH.RO_QUERY). The server rejects any write in this path."""
    t0 = time.time()
    res = _wrap(lambda: graph(graph_name).ro_query(query, params or {}))
    return res.header, res.result_set, round((time.time() - t0) * 1000, 2)


def rw(query: str, params: dict | None = None, graph_name: str | None = None):
    return _wrap(lambda: graph(graph_name).query(query, params or {})).result_set


def revision(graph_name: str | None = None) -> int:
    _, rows, _ = ro("MATCH (m:Meta {id:'meta'}) RETURN m.revision", graph_name=graph_name)
    return int(rows[0][0]) if rows else 0


def bump_revision(reason: str, graph_name: str | None = None) -> int:
    rows = rw("MERGE (m:Meta {id:'meta'}) ON CREATE SET m.revision = 0 "
              "SET m.revision = m.revision + 1, m.last_change = $r, m.changed_at = $t RETURN m.revision",
              {"r": reason, "t": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, graph_name)
    return int(rows[0][0])


def copy_graph(src: str, dst: str) -> None:
    """Isolated What-if copy via GRAPH.COPY (verified on the pinned runtime at Gate 0)."""
    _wrap(lambda: _conn().connection.execute_command("GRAPH.COPY", src, dst))


def delete_graph(name: str) -> None:
    try:
        _wrap(lambda: graph(name).delete())
    except GraphUnavailable:
        raise
    except Exception:
        pass


def ping() -> bool:
    try:
        return bool(_wrap(lambda: _conn().connection.ping()))
    except GraphUnavailable:
        return False
