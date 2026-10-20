import socket

import pytest

BLOCKED = "Offline tests must mock provider calls; network access is disabled"


def test_guard_blocks_non_loopback_ipv4():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setblocking(False)
        with pytest.raises(AssertionError, match=BLOCKED):
            s.connect(("203.0.113.1", 443))


def test_guard_allows_socketpair():
    a, b = socket.socketpair()
    with a, b:
        a.sendall(b"x")
        assert b.recv(1) == b"x"


def test_guard_blocks_non_loopback_ipv6():
    with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
        s.setblocking(False)
        with pytest.raises(AssertionError, match=BLOCKED):
            s.connect(("2001:db8::1", 443, 0, 0))
