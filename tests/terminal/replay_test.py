"""Headless tests for the replay helpers."""

import json
import tempfile
from pathlib import Path

import pytest

from src.utils.replay import ReplayPlayer, ReplayRecorder


class DummyScene:
    def __init__(self) -> None:
        self.state = {"phase": "Idle", "phase_index": 0}
        self.events: list[dict] = []
        self._replay_phase = "Idle"

    def capture_replay_state(self) -> dict:
        return dict(self.state)

    def apply_replay_event(self, event: dict) -> None:
        self.events.append(event)
        if event.get("type") == "action" and event.get("name") == "set_phase":
            self.state["phase"] = event.get("value")
            self._replay_phase = event.get("value")


def test_replay_file_roundtrip() -> None:
    scene = DummyScene()
    recorder = ReplayRecorder(scene, fixed_dt=0.016, snapshot_interval=0.25)
    recorder.record_event("action", name="set_phase", value="Walk")
    recorder.record_snapshot(0.0, scene.capture_replay_state())
    recorder.add_assertion("end", "_replay_phase", "Walk")
    scene.state["phase"] = "Walk"
    scene._replay_phase = "Walk"
    recorder.record_snapshot(0.25, scene.capture_replay_state())

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.replay.json"
        recorder.save(path)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["version"] == 1
        assert data["events"][0]["name"] == "set_phase"
        assert data["assertions"][0]["expected"] == "Walk"


def test_player_dispatches_events_in_order() -> None:
    scene = DummyScene()
    recorder = ReplayRecorder(scene, fixed_dt=0.016, snapshot_interval=10.0)
    recorder.record_event("action", t=0.0, name="set_phase", value="Walk")
    recorder.record_event("action", t=0.1, name="set_phase", value="Run")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.replay.json"
        recorder.save(path)
        player = ReplayPlayer(path)
        assert player.fixed_dt == pytest.approx(0.016)
        player.tick(0.05, scene)
        assert scene.state["phase"] == "Walk"
        player.tick(0.1, scene)
        assert scene.state["phase"] == "Run"


def test_player_reports_snapshot_mismatch() -> None:
    scene = DummyScene()
    recorder = ReplayRecorder(scene, fixed_dt=0.016, snapshot_interval=0.1)
    recorder.record_snapshot(0.0, {"phase": "Idle", "phase_index": 0})

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.replay.json"
        recorder.save(path)
        player = ReplayPlayer(path)
        scene.state["phase"] = "Walk"
        player.tick(0.05, scene)
        errors = player.errors
        assert any("snapshot@" in error for error in errors)


def test_finalize_reports_assertion_failure() -> None:
    scene = DummyScene()
    recorder = ReplayRecorder(scene, fixed_dt=0.016, snapshot_interval=10.0)
    recorder.add_assertion("end", "_replay_phase", "Run")
    scene._replay_phase = "Idle"

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.replay.json"
        recorder.save(path)
        player = ReplayPlayer(path)
        errors = player.finalize(scene)
        assert any("assertion _replay_phase" in error for error in errors)


def test_finalize_reports_success() -> None:
    scene = DummyScene()
    recorder = ReplayRecorder(scene, fixed_dt=0.016, snapshot_interval=10.0)
    recorder.add_assertion("end", "_replay_phase", "Idle")
    scene._replay_phase = "Idle"

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.replay.json"
        recorder.save(path)
        player = ReplayPlayer(path)
        errors = player.finalize(scene)
        assert errors == []


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
