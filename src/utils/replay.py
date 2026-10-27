"""Deterministic replay helpers for visual sandboxes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ReplayRecorder:
    """Collect replay events, snapshots and assertions for a sandbox."""

    def __init__(
        self,
        scene: Any,
        fixed_dt: float = 0.016,
        snapshot_interval: float = 0.25,
        seed: int | None = None,
    ) -> None:
        self.scene = scene
        self.fixed_dt = float(fixed_dt)
        self.snapshot_interval = float(snapshot_interval)
        self.seed = seed
        self.events: list[dict[str, Any]] = []
        self.snapshots: list[dict[str, Any]] = []
        self.assertions: list[dict[str, Any]] = []
        self._elapsed: float = 0.0
        self._next_snapshot: float = 0.0

    @property
    def elapsed(self) -> float:
        return self._elapsed

    def tick(self, dt: float) -> None:
        self._elapsed += float(dt)
        if self._elapsed >= self._next_snapshot:
            self.record_snapshot(self._elapsed, self._capture_state())
            self._next_snapshot += self.snapshot_interval

    def record_event(self, event_type: str, t: float | None = None, **payload: Any) -> None:
        self.events.append({"t": round(self._elapsed if t is None else t, 6), "type": event_type, **payload})

    def record_snapshot(self, t: float, state: dict[str, Any]) -> None:
        self.snapshots.append({"t": round(float(t), 6), "state": state})

    def add_assertion(self, at: str, path: str, expected: Any) -> None:
        self.assertions.append({"at": at, "path": path, "expected": expected})

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "scene": getattr(self.scene, "_replay_scene_name", type(self.scene).__name__),
            "fixed_dt": self.fixed_dt,
            "snapshot_interval": self.snapshot_interval,
            "seed": self.seed,
            "events": self.events,
            "snapshots": self.snapshots,
            "assertions": self.assertions,
        }
        target.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def _capture_state(self) -> dict[str, Any]:
        capture = getattr(self.scene, "capture_replay_state", None)
        if callable(capture):
            try:
                return capture()
            except Exception:  # noqa: BLE001
                return {}
        return {}


class ReplayPlayer:
    """Replay a recorded sandbox scenario and validate assertions."""

    def __init__(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = int(data.get("version", 1))
        self.scene_name = data.get("scene")
        self.fixed_dt = float(data.get("fixed_dt", 0.016))
        self.events = list(data.get("events", []))
        self.snapshots = list(data.get("snapshots", []))
        self.assertions = list(data.get("assertions", []))
        self._event_index = 0
        self._snapshot_index = 0
        self._elapsed = 0.0
        self._errors: list[str] = []
        self._snapshot_mismatches: list[str] = []

    @property
    def elapsed(self) -> float:
        return self._elapsed

    @property
    def errors(self) -> list[str]:
        return self._errors + self._snapshot_mismatches

    def tick(self, dt: float, scene: Any) -> None:
        self._elapsed += float(dt)
        while self._event_index < len(self.events):
            event = self.events[self._event_index]
            if float(event.get("t", 0.0)) <= self._elapsed + 1e-9:
                self._dispatch(scene, event)
                self._event_index += 1
            else:
                break

        # Validate the nearest recorded snapshot once its time has passed.
        while self._snapshot_index < len(self.snapshots):
            snapshot = self.snapshots[self._snapshot_index]
            if float(snapshot.get("t", 0.0)) <= self._elapsed + 1e-9:
                actual = self._capture_state(scene)
                expected = snapshot.get("state", {})
                if actual != expected:
                    self._snapshot_mismatches.append(
                        f"snapshot@{snapshot.get('t')}: expected {expected}, got {actual}"
                    )
                self._snapshot_index += 1
            else:
                break

    def finalize(self, scene: Any) -> list[str]:
        errors = list(self._snapshot_mismatches)
        for assertion in self.assertions:
            if assertion.get("at") != "end":
                continue
            actual = self._get_path(scene, assertion.get("path", ""))
            expected = assertion.get("expected")
            if actual != expected:
                errors.append(f"assertion {assertion.get('path')}: expected {expected}, got {actual}")
        self._errors = errors
        return errors

    @staticmethod
    def _capture_state(scene: Any) -> dict[str, Any]:
        capture = getattr(scene, "capture_replay_state", None)
        if callable(capture):
            try:
                return capture()
            except Exception:  # noqa: BLE001
                return {}
        return {}

    @staticmethod
    def _dispatch(scene: Any, event: dict[str, Any]) -> None:
        handler = getattr(scene, "apply_replay_event", None)
        if callable(handler):
            try:
                handler(event)
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    def _get_path(obj: Any, path: str) -> Any:
        current = obj
        for part in path.split("."):
            if not part:
                continue
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current
