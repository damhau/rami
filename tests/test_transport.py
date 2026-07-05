"""End-to-end transport: REST create/join + a WebSocket round of play."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from rami.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


def _recv_until(ws, pred: Callable[[dict], bool], limit: int = 20) -> dict:
    for _ in range(limit):
        msg = ws.receive_json()
        if pred(msg):
            return msg
    raise AssertionError("expected message not received")


def _create_table(client, name: str) -> dict:
    r = client.post("/api/v1/tables", json={"name": name})
    assert r.status_code == 201
    return r.json()


def test_create_and_join_table_rest():
    with TestClient(create_app()) as client:
        a = _create_table(client, "Alice")
        assert a["seat"] == 0
        assert a["host"] is True
        b = client.post(f"/api/v1/tables/{a['code']}/join", json={"name": "Bob"}).json()
        assert b["seat"] == 1
        summary = client.get(f"/api/v1/tables/{a['code']}").json()
        assert summary["phase"] == "lobby"
        assert [p["name"] for p in summary["players"]] == ["Alice", "Bob"]


def test_join_unknown_table_404():
    with TestClient(create_app()) as client:
        r = client.post("/api/v1/tables/RAMI-NOPE/join", json={"name": "X"})
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "table_not_found"


def test_bad_token_is_rejected(client):
    a = _create_table(client, "Alice")
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(f"/ws/table/{a['code']}?token=bogus") as ws,
    ):
        ws.receive_json()


def test_full_ws_round_start_and_turn_enforcement(client):
    a = _create_table(client, "Alice")
    b = client.post(f"/api/v1/tables/{a['code']}/join", json={"name": "Bob"}).json()

    with (
        client.websocket_connect(f"/ws/table/{a['code']}?token={a['token']}") as wa,
        client.websocket_connect(f"/ws/table/{a['code']}?token={b['token']}") as wb,
    ):
        # Each side first sees a lobby snapshot.
        _recv_until(wa, lambda m: m["type"] == "snapshot")
        _recv_until(wb, lambda m: m["type"] == "snapshot")

        # Host starts the game.
        wa.send_json({"type": "start"})
        sa = _recv_until(wa, lambda m: m.get("phase") == "await_draw")
        sb = _recv_until(wb, lambda m: m.get("phase") == "await_draw")

        assert sa["you"] == 0
        assert sb["you"] == 1
        assert len(sa["your_hand"]) == 13
        # Opponents are redacted to a count only.
        assert sa["players"][1]["hand_count"] == 13
        assert sa["contract"]["label"] == "1 triplet"

        # Dealer is seat 0, so seat 1 (Bob) starts. Alice acting is illegal.
        assert sa["turn_seat"] == 1
        wa.send_json({"type": "draw_stock"})
        err = _recv_until(wa, lambda m: m["type"] == "error")
        assert err["code"] == "not_your_turn"


def test_non_host_cannot_start(client):
    a = _create_table(client, "Alice")
    b = client.post(f"/api/v1/tables/{a['code']}/join", json={"name": "Bob"}).json()
    with (
        client.websocket_connect(f"/ws/table/{a['code']}?token={a['token']}") as wa,
        client.websocket_connect(f"/ws/table/{a['code']}?token={b['token']}") as wb,
    ):
        _recv_until(wa, lambda m: m["type"] == "snapshot")
        _recv_until(wb, lambda m: m["type"] == "snapshot")
        wb.send_json({"type": "start"})
        err = _recv_until(wb, lambda m: m["type"] == "error")
        assert err["code"] == "table_state"
