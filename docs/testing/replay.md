# Replay and deterministic sandbox scenarios

Visual sandboxes can record and replay deterministic scenarios for regression
testing.

## Usage

Record:
```bash
./venv/bin/python -m tests.panda.animation_sandbox --record tests/artifacts/anim_state.replay.json --duration 3
```

Replay:
```bash
./venv/bin/python -m tests.panda.animation_sandbox --replay tests/artifacts/anim_state.replay.json --duration 3
```

## Format

Replay files are JSON with `events`, `snapshots` and `assertions`. Artefacts are
stored under `tests/artifacts/` and ignored by git.

## Limitations

Replay is deterministic only when the sandbox uses a fixed update dt and does not
depend on wall-clock time or external input.

Source: `src/utils/replay.py`, `tests/panda/animation_sandbox.py`
Tests: `tests/terminal/replay_test.py`
