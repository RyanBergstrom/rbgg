"""Scratch script: drive a 3-player Bus game through setup via the real HTTP
routes and attempt a human select_action move, printing every legal-move
payload along the way so we can compare exactly what the frontend receives.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


def post(path, body=None):
    resp = client.post(path, json=body or {})
    print(f"POST {path} -> {resp.status_code}")
    return resp


def main():
    resp = post("/api/v1/moves/start-session/bus", {"playerCount": 3})
    body = resp.json()
    session_id = body["session_id"]
    print("session_id", session_id)

    def legal_moves():
        r = post("/api/v1/moves/legal-moves", {"sessionId": session_id})
        return r.json()

    def current_state():
        r = client.get(f"/api/v1/games/bus?session_id={session_id}")
        return r.json()["state"]["game_data"]

    # Drive through setup: buildings (2 per player), first route, second route
    # for all 3 players, using whatever human/bot each phase expects. We use
    # the AI endpoint for everyone except keep narrating which player acted.
    phase = None
    guard = 0
    while True:
        guard += 1
        if guard > 200:
            print("guard tripped — too many iterations")
            break
        state = current_state()
        phase = state["current_phase"]
        current_player = state["current_player"]
        print(f"--- phase={phase} current_player={current_player}")
        if phase == "ACTION_SELECTION":
            break
        moves_resp = legal_moves()
        moves = moves_resp.get("legal_moves", [])
        if not moves:
            print("NO LEGAL MOVES — stuck", json.dumps(moves_resp, indent=2)[:2000])
            break
        move = moves[0]
        print("submitting", move)
        r = client.post(f"/api/v1/moves/{session_id}/move", json=move)
        print("  ->", r.status_code, r.json() if r.status_code != 200 else "ok")
        if r.status_code != 200:
            print(json.dumps(r.json(), indent=2))
            return

    # Now in ACTION_SELECTION. Print legal moves for whoever is current.
    state = current_state()
    print("ACTION_SELECTION current_player:", state["current_player"])
    moves_resp = legal_moves()
    print(json.dumps(moves_resp.get("legal_moves", []), indent=2))

    # Try submitting the first select_action move for the current player.
    moves = moves_resp.get("legal_moves", [])
    select_moves = [m for m in moves if m["type"] == "select_action"]
    if not select_moves:
        print("NO select_action MOVES AVAILABLE")
        return
    move = select_moves[0]
    print("Submitting:", move)
    r = client.post(f"/api/v1/moves/{session_id}/move", json=move)
    print(r.status_code, r.json())


if __name__ == "__main__":
    main()
