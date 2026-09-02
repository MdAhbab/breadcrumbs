"""
Building the demo world without making the API wait for it.

A cold start commits nearly seven hundred corpus documents, runs a trusted-dealer
ceremony, folds three accumulator epochs, produces two verifiable-delay proofs
and trains a detector through four gate decisions. That is forty seconds of real
work, and it is real work rather than a slow import — none of it can be made
instant without making it fake.

What it must not do is hold the socket closed for forty seconds. A process
manager reads that as a failed start and kills it, which is exactly what
happened; and a developer reads it as a hang. So the seed runs on a background
thread and the API answers from the first moment, refusing data requests with a
503 and a sentence saying what it is doing and roughly how long is left.

The refusal is deliberate rather than serving empty lists. An empty list is a
statement that there is nothing, and while the world is building that statement
is false.
"""

from __future__ import annotations

import threading
import time
from typing import Any

_lock = threading.Lock()
_state: dict[str, Any] = {
    "state": "building",
    "detail": "building the world from the corpus",
    "started_at": time.time(),
    "finished_at": None,
    "result": None,
    "error": None,
}

# Measured on the machine this was written on. Only ever used to tell a waiting
# user roughly how long is left, never to decide anything.
TYPICAL_SECONDS = 45


def snapshot() -> dict[str, Any]:
    with _lock:
        elapsed = (
            (_state["finished_at"] or time.time()) - _state["started_at"]
        )
        return {
            "state": _state["state"],
            "detail": _state["detail"],
            "elapsed_seconds": round(elapsed, 1),
            "typical_seconds": TYPICAL_SECONDS,
            "result": _state["result"],
            "error": _state["error"],
        }


def ready() -> bool:
    with _lock:
        return _state["state"] == "ready"


def failed() -> bool:
    with _lock:
        return _state["state"] == "failed"


def _set(**fields: Any) -> None:
    with _lock:
        _state.update(fields)


def build(session_factory: Any) -> None:
    """Run the seed on this thread and record how it went."""
    from .seed import seed

    _set(state="building", started_at=time.time(), finished_at=None, error=None)
    session = session_factory()
    try:
        result = seed(session)
        _set(
            state="ready",
            detail=result.get("status", "ready"),
            result=result,
            finished_at=time.time(),
        )
        print(f"[breadcrumbs] world state: {result['status']}")
    except Exception as exc:  # noqa: BLE001 - the API must report this, not die of it
        _set(
            state="failed",
            detail="the world could not be built",
            error=f"{type(exc).__name__}: {exc}",
            finished_at=time.time(),
        )
        print(f"[breadcrumbs] world build FAILED: {exc}")
    finally:
        session.close()


def start(session_factory: Any) -> threading.Thread:
    thread = threading.Thread(
        target=build, args=(session_factory,), name="breadcrumbs-seed", daemon=True
    )
    thread.start()
    return thread


def waiting_message() -> str:
    snap = snapshot()
    if snap["state"] == "failed":
        return f"The demo world could not be built: {snap['error']}"
    left = max(0, TYPICAL_SECONDS - snap["elapsed_seconds"])
    return (
        "The ledger is still being built from the corpus — committing documents, "
        "running the accumulator ceremony and training the detector. About "
        f"{int(left)}s left. This happens once per start."
    )


def wait(timeout: float = 300.0) -> dict[str, Any]:
    """
    Block until the world is built. For tests and for scripts.

    The API never calls this — the whole point is that it does not wait — but a
    test that starts the app and immediately asks for records needs the world to
    exist, and polling the health endpoint from every fixture would be worse.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if ready() or failed():
            break
        time.sleep(0.25)
    snap = snapshot()
    if snap["state"] != "ready":
        raise RuntimeError(f"world not ready after {timeout}s: {snap}")
    return snap
