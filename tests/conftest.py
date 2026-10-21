import os
import socket

import pytest

from crack.config import DEFAULT_SETTINGS

_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_local(address) -> bool:
    if isinstance(address, (str, bytes)):  # AF_UNIX path
        return True
    return isinstance(address, tuple) and bool(address) and address[0] in _LOOPBACK_HOSTS


@pytest.fixture(autouse=True)
def _offline_network_guard(request, monkeypatch):
    """A test without the live marker cannot spend API quota accidentally.

    Loopback stays allowed: on Windows, asyncio's event loop builds its self-pipe
    with socket.socketpair(), whose fallback connects to 127.0.0.1. Blocking that
    breaks every test that starts an event loop (e.g. Starlette's TestClient).
    """
    if request.node.get_closest_marker("live"):
        return

    def guarded(original):
        def connect(self, address, *args):
            if _is_local(address):
                return original(self, address, *args)
            raise AssertionError("Offline tests must mock provider calls; network access is disabled")
        return connect

    monkeypatch.setattr(socket.socket, "connect", guarded(socket.socket.connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(socket.socket.connect_ex))


@pytest.fixture(autouse=True)
def _live_gate(request):
    """Skip any live test unless DOUBLETAKE_ALLOW_LIVE=1 is explicitly set.

    An API key being present is NOT sufficient — it must be paired with the
    opt-in flag so live runs are always a conscious decision, not an accident.
    """
    if not request.node.get_closest_marker("live"):
        return
    if os.getenv("DOUBLETAKE_ALLOW_LIVE") != "1":
        pytest.skip(
            "Live tests consume paid API quota and require explicit opt-in. "
            "Set DOUBLETAKE_ALLOW_LIVE=1 to run them. "
            "Routine verification: py -3.11 -m pytest -q -m 'not live'",
        )
    from crack.providers import resolve_api_key, resolve_backend
    backend_req = os.getenv("DOUBLETAKE_BACKEND") or "auto"
    backend = resolve_backend(backend_req)
    key_val, key_name = resolve_api_key(backend)
    if not key_val:
        pytest.skip(f"Live test skipped: {key_name} not set for backend '{backend}'")
