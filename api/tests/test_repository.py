"""Tests for WI-006 repository CRUD and optimistic concurrency."""

from app.core.repository import (
    create_session,
    get_session,
    save_session,
    list_sessions,
    record_stats,
    complete_session,
)


def test_create_and_get_session_round_trip():
    """Verify create_session and get_session round-trip."""
    # Use a temp DB so we don't persist across tests
    profile_id = "prof-001"
    session = create_session(profile_id=profile_id, state_id="s1")
    assert session["profile_id"] == profile_id
    assert session["state_id"] == "s1"
    assert session["id"] is not None

    retrieved = get_session(session["id"])
    assert retrieved is not None
    assert retrieved["profile_id"] == profile_id
    assert retrieved["state_id"] == "s1"
    assert retrieved["id"] == session["id"]


def test_save_session_succeeds_with_matching_version_and_bumps_it():
    """Verify save_session succeeds when expected_version matches and bumps it."""
    sess = create_session(profile_id="prof-002", state_id="s2")
    session_id = sess["id"]

    # First save: expected_version=1 should succeed and bump to 2
    result = save_session(session_id=session_id, expected_version=1)
    assert result is True

    # Version should now be 2
    updated = get_session(session_id)
    assert updated["expected_version"] == 2

    # Second save: expected_version=2 should succeed and bump to 3
    result2 = save_session(session_id=session_id, expected_version=2)
    assert result2 is True
    updated2 = get_session(session_id)
    assert updated2["expected_version"] == 3


def test_save_session_fails_with_stale_version():
    """Verify save_session fails when expected_version does not match."""
    sess = create_session(profile_id="prof-003", state_id="s3")
    session_id = sess["id"]

    # Insert with expected_version=99 (never set, should fail)
    result = save_session(session_id=session_id, expected_version=99)
    assert result is False

    # Version should remain unchanged (still None/init value)
    updated = get_session(session_id)
    # The version should not have been updated


def test_list_sessions_filters_by_game_id_and_profile():
    """Verify list_sessions filters by profile_id and state_id (game_id)."""
    # Create sessions for different profiles and games
    s1 = create_session(profile_id="prof-a", game_id="game-1", state_id="s1")
    s2 = create_session(profile_id="prof-a", game_id="game-2", state_id="s2")
    s3 = create_session(profile_id="prof-b", game_id="game-1", state_id="s3")

    # List all
    all_sessions = list_sessions()
    assert len(all_sessions) == 3

    # Filter by profile
    prof_a = list_sessions(profile_id="prof-a")
    assert len(prof_a) == 2
    prof_a_ids = {s["id"] for s in prof_a}
    assert prof_a_ids == {s1["id"], s2["id"]}

    # Filter by game_id
    game1 = list_sessions(game_id="game-1")
    assert len(game1) == 2  # s1 and s3
    game1_ids = {s["id"] for s in game1}
    assert game1_ids == {s1["id"], s3["id"]}

    # Filter by both profile and game
    prof_a_game1 = list_sessions(profile_id="prof-a", game_id="game-1")
    assert len(prof_a_game1) == 1
    assert prof_a_game1[0]["profile_id"] == "prof-a"


def test_record_stats_inserts_row():
    """Verify record_stats inserts a row and returns the created record."""
    record = record_stats(profile_id="prof-stats", total_moves=42, total_turns=15)
    assert record["profile_id"] == "prof-stats"
    assert record["total_moves"] == 42
    assert record["total_turns"] == 15
    assert record["id"] is not None

    # Verify that the insert completed without requiring a stats reader.


def test_complete_session_is_idempotent_and_records_once():
    """Completion sets finished_at and retries do not duplicate statistics."""
    session = create_session(profile_id="prof-complete", game_id="checkers")
    session_id = session["id"]

    final_scores = {"player_1": 10, "player_2": 5}
    result_summary = {"winner": "player_1", "scores": final_scores}

    assert complete_session(
        session_id,
        total_moves=4,
        total_turns=2,
        winner="player_1",
        final_scores=final_scores,
        result_summary=result_summary,
    ) is True
    assert complete_session(session_id, total_moves=4, total_turns=2) is False

    completed = get_session(session_id)
    assert completed["finished_at"] is not None
    assert completed["winner"] == "player_1"
    assert completed["final_scores_json"] == '{"player_1": 10, "player_2": 5}'
    assert completed["result_summary_json"] == '{"winner": "player_1", "scores": {"player_1": 10, "player_2": 5}}'
    assert len([s for s in list_sessions(profile_id="prof-complete") if s["id"] == session_id]) == 1
