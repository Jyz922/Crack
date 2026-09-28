import os

import pytest

from crack.config import DEFAULT_SETTINGS


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

