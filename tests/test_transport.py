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


def test_version_endpoint_reports_package_version():
    from rami.core.config import get_version

    with TestClient(create_app()) as client:
        r = client.get("/api/v1/version")
        assert r.status_code == 200
        assert r.json() == {"version": get_version()}


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

        # The opening seat is random; whoever is NOT on turn drawing is illegal.
        turn = sa["turn_seat"]
        off = wb if turn == 0 else wa
        off.send_json({"type": "draw_stock"})
        err = _recv_until(off, lambda m: m["type"] == "error")
        assert err["code"] == "not_your_turn"


def test_reconnect_with_same_token_resumes(client):
    a = _create_table(client, "Alice")
    b = client.post(f"/api/v1/tables/{a['code']}/join", json={"name": "Bob"}).json()

    with client.websocket_connect(f"/ws/table/{a['code']}?token={a['token']}") as wa:
        _recv_until(wa, lambda m: m["type"] == "snapshot")
        with client.websocket_connect(f"/ws/table/{a['code']}?token={b['token']}") as wb:
            _recv_until(wb, lambda m: m["type"] == "snapshot")
            wa.send_json({"type": "start"})
            _recv_until(wa, lambda m: m.get("phase") == "await_draw")
        # Bob dropped. Reconnecting with the same token re-attaches to his seat.
        with client.websocket_connect(f"/ws/table/{a['code']}?token={b['token']}") as wb2:
            snap = _recv_until(wb2, lambda m: m["type"] == "snapshot")
            assert snap["you"] == b["seat"]
            assert snap["phase"] == "await_draw"  # game state preserved
            assert len(snap["your_hand"]) == 13
            assert snap["players"][b["seat"]]["connected"] is True


def test_disconnected_seat_is_auto_played(client, monkeypatch):
    import rami.realtime.ws as wsmod

    monkeypatch.setattr(wsmod, "DISCONNECT_TIMEOUT_S", 0.3)
    monkeypatch.setattr(wsmod, "AUTOPLAY_STEP_S", 0.05)
    # The opening stock draw may offer the other (connected) seat a free card,
    # which briefly holds the drawer; keep that window short for the test.
    monkeypatch.setattr(wsmod, "FREE_CARD_TIMEOUT_S", 0.3)

    a = _create_table(client, "Alice")
    b = client.post(f"/api/v1/tables/{a['code']}/join", json={"name": "Bob"}).json()

    cm = {
        0: client.websocket_connect(f"/ws/table/{a['code']}?token={a['token']}"),
        1: client.websocket_connect(f"/ws/table/{a['code']}?token={b['token']}"),
    }
    ws = {seat: c.__enter__() for seat, c in cm.items()}
    try:
        _recv_until(ws[0], lambda m: m["type"] == "snapshot")
        _recv_until(ws[1], lambda m: m["type"] == "snapshot")
        ws[0].send_json({"type": "start"})
        sa = _recv_until(ws[0], lambda m: m.get("phase") == "await_draw")
        _recv_until(ws[1], lambda m: m.get("phase") == "await_draw")

        turn = sa["turn_seat"]
        # The player on turn drops; the server auto-plays and passes the turn on.
        cm.pop(turn).__exit__(None, None, None)
        passed = _recv_until(
            ws[1 - turn],
            lambda m: m["type"] == "snapshot" and m.get("turn_seat") != turn,
            limit=40,
        )
        assert passed["turn_seat"] != turn
    finally:
        for c in cm.values():
            c.__exit__(None, None, None)


def test_bot_drawer_pauses_for_human_free_card_decision():
    # Issue #10: while a human is being offered the refused discard, the bot
    # drawer must not act (its discard would close the offer) — the table waits
    # on the human. A bot at the head decides its own free card as before.
    import rami.realtime.ws as wsmod
    from conftest import card
    from rami.game.cards import Suit
    from rami.game.state import FreeCardOffer, GameState, PlayerState
    from rami.game.state import Phase as P
    from rami.tables.manager import GameSession, Seat

    seats = [
        Seat(seat=0, name="Bot", token="a", connected=True, is_bot=True),
        Seat(seat=1, name="Human", token="b", connected=True, is_bot=False),
    ]
    state = GameState(
        players=[PlayerState(0, "Bot"), PlayerState(1, "Human")],
        phase=P.AWAIT_DISCARD,
        turn_seat=0,
        discard=[card(Suit.HEARTS, 9, 5)],
        free_card=FreeCardOffer(pending_seats=[1], resume_seat=0),
    )
    session = GameSession(code="X", min_players=2, max_players=2, seats=seats, state=state)

    assert wsmod._bot_seat_to_act(session, state) is None  # bot drawer paused
    assert wsmod._waiting_human_seat(session) == 1  # table waits on the human

    # If the head is a bot, it decides its own free card immediately.
    seats[1].is_bot = True
    assert wsmod._bot_seat_to_act(session, state) == 1
    assert wsmod._waiting_human_seat(session) is None


def test_solo_pause_resume_over_websocket(client):
    # Issue #25: the lone human of a solo game can pause; bots hold, game
    # intents are rejected while paused, and resume restores play.
    r = client.post("/api/v1/tables/solo", json={"name": "Solo", "bots": 1})
    assert r.status_code == 201
    a = r.json()
    with client.websocket_connect(f"/ws/table/{a['code']}?token={a['token']}") as ws:
        _recv_until(ws, lambda m: m["type"] == "snapshot")
        ws.send_json({"type": "pause"})
        snap = _recv_until(ws, lambda m: m["type"] == "snapshot" and m.get("paused") is True)
        assert snap["paused"] is True
        # Game intents are rejected while paused.
        ws.send_json({"type": "draw_stock"})
        err = _recv_until(ws, lambda m: m["type"] == "error")
        assert "paus" in err["message"]
        ws.send_json({"type": "resume"})
        snap = _recv_until(ws, lambda m: m["type"] == "snapshot" and m.get("paused") is False)
        assert snap["paused"] is False


def test_pause_is_rejected_in_multiplayer(client):
    a = _create_table(client, "Alice")
    b = client.post(f"/api/v1/tables/{a['code']}/join", json={"name": "Bob"}).json()
    with (
        client.websocket_connect(f"/ws/table/{a['code']}?token={a['token']}") as wa,
        client.websocket_connect(f"/ws/table/{a['code']}?token={b['token']}") as wb,
    ):
        _recv_until(wa, lambda m: m["type"] == "snapshot")
        _recv_until(wb, lambda m: m["type"] == "snapshot")
        wa.send_json({"type": "start"})
        _recv_until(wa, lambda m: m.get("phase") == "await_draw")
        wa.send_json({"type": "pause"})
        err = _recv_until(wa, lambda m: m["type"] == "error")
        assert "solo" in err["message"]


def test_paused_session_holds_bots_and_idle_timer():
    # While paused, _run_bots must not act and _schedule_idle must not arm; a
    # solo table never arms the idle autoplay at all (issue #25).
    import rami.realtime.ws as wsmod
    from rami.tables.manager import GameSession, Seat

    seats = [
        Seat(seat=0, name="Human", token="a", connected=True, is_bot=False),
        Seat(seat=1, name="Bot", token="b", connected=True, is_bot=True),
    ]
    session = GameSession(code="Y", min_players=2, max_players=2, seats=seats)
    session._rebuild_lobby_state()
    session.start()
    assert session.single_human
    # Solo: no idle timer, paused or not (the game waits for the human).
    wsmod._schedule_idle(session)
    assert wsmod._idle_tasks.get("Y") is None
    session.paused = True
    wsmod._schedule_idle(session)
    assert wsmod._idle_tasks.get("Y") is None


def test_run_bots_loop_guard_terminates_a_stuck_policy(monkeypatch):
    # Issue #16: _run_bots is awaited from every message handler, so a policy
    # cycling without progress (DrawDiscard ↔ ReturnDiscard) used to hang the
    # whole table. The MAX_POLICY_MOVES guard must break out instead.
    import asyncio

    import rami.realtime.ws as wsmod
    from conftest import card
    from rami.game.cards import Suit
    from rami.game.intents import DrawDiscard, ReturnDiscard
    from rami.game.state import GameState, PlayerState
    from rami.game.state import Phase as P
    from rami.tables.manager import GameSession, Seat

    monkeypatch.setattr(wsmod, "BOT_MOVE_DELAY_S", 0)

    calls = {"n": 0}

    def stuck_policy(state, seat):  # alternates take / put-back forever
        calls["n"] += 1
        return ReturnDiscard(seat) if state.taken_from_discard_id is not None else DrawDiscard(seat)

    monkeypatch.setattr(wsmod.ai, "next_bot_intent", stuck_policy)

    seats = [Seat(seat=0, name="Bot", token="a", connected=True, is_bot=True)]
    state = GameState(
        players=[PlayerState(0, "Bot", hand=[card(Suit.SPADES, 5, 1)])],
        phase=P.AWAIT_DRAW,
        turn_seat=0,
        discard=[card(Suit.HEARTS, 9, 2)],
        stock=[card(Suit.CLUBS, 3, 3)],
    )
    session = GameSession(code="X", min_players=1, max_players=1, seats=seats, state=state)

    # Must return on its own (guard) — a hang here would time out the test run.
    asyncio.run(asyncio.wait_for(wsmod._run_bots(session), timeout=30))
    assert calls["n"] == wsmod.MAX_POLICY_MOVES  # spun exactly to the cap, then broke


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
