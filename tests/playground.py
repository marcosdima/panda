"""Interactive playground selector for the test scenes.

The playground is a Panda3D application that lists every scene registered in
``tests.registry`` and launches the chosen one in an isolated subprocess. No
scene runs inside the playground process, so physics worlds, lights, inputs and
cameras stay clean between runs.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import threading
import time
from pathlib import Path

from direct.gui.OnscreenText import OnscreenText

from src import game
from src.ui import (
    UIButton,
    UIList,
    UIPanel,
    UIRow,
    UIScrollContainer,
    UITheme,
)
from tests.__test import Test

from .registry import SCENE_REGISTRY

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TIMEOUT = 120


def run_scene(key: str, timeout: int) -> tuple[int, str, bool, float]:
    """Launch ``key`` in an isolated subprocess and return its outcome."""
    if key not in SCENE_REGISTRY:
        raise KeyError(f"Unknown scene key: {key}")
    title, _category, scene_cls = SCENE_REGISTRY[key]
    module = scene_cls.__module__
    cmd = [sys.executable, "-u", "-m", module]
    started = time.monotonic()
    timed_out = False
    output = ""
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            output, _ = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            output, _ = proc.communicate()
        exit_code = proc.returncode
    except Exception as exc:  # noqa: BLE001
        output = str(exc)
        exit_code = 1
    duration = time.monotonic() - started
    print(f"\n===== {key} ({title}) exit={exit_code} duration={duration:.1f}s =====")
    if timed_out:
        print(f"TIMEOUT after {timeout}s: process killed.")
    tail = [line for line in (output or "").splitlines() if line.strip()][-30:]
    for line in tail:
        print(line)
    print("===== end =====")
    return exit_code, output or "", timed_out, duration


class Playground(Test):
    """In-window menu that launches registered scenes as subprocesses."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        super().__init__()
        self.timeout = timeout
        self._visual_keys = sorted(
            key for key, value in SCENE_REGISTRY.items() if value[1] == "visual"
        )
        self._buffer = ""
        self._running_key: str | None = None
        self._last_key: str | None = None
        self._launch_started: float = 0.0
        self._result: tuple[int, str, bool, float] | None = None
        self._worker: threading.Thread | None = None
        self._ui_components: list = []
        self._theme = UITheme()
        self._texts: list[OnscreenText] = []
        self._status_text: OnscreenText | None = None

    def _clear_ui(self) -> None:
        for component in list(self._ui_components):
            try:
                component.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._ui_components.clear()
        for text in self._texts:
            try:
                text.destroy()
            except Exception:  # noqa: BLE001
                pass
        self._texts.clear()
        self._status_text = None

    def _build_menu(self, status: str | None = None) -> None:
        self._clear_ui()
        import builtins

        base = getattr(builtins, "base", None)
        parent = getattr(base, "aspect2d", None) if base is not None else None
        if parent is None:
            return

        title = OnscreenText(
            text="Panda Playground",
            pos=(0.0, 0.93),
            scale=self._theme.title_scale,
            fg=(0.35, 0.85, 1.0, 1.0),
        )
        subtitle = OnscreenText(
            text="Select a scene by number or click the list, then press Enter.",
            pos=(0.0, 0.86),
            scale=self._theme.body_scale,
            fg=(0.75, 0.75, 0.75, 1.0),
        )
        self._texts.extend([title, subtitle])

        left_panel = UIPanel(
            parent=parent,
            title="Scenes",
            width=1.05,
            height=0.95,
            theme=self._theme,
            owner=self,
            pos=(-0.55, 0.0, -0.05),
        )
        items = [
            (f"{index:2d}. {SCENE_REGISTRY[key][0]}  [{key}]", key)
            for index, key in enumerate(self._visual_keys, start=1)
        ]
        container = UIScrollContainer(
            parent=left_panel.content_parent,
            width=0.95,
            height=0.78,
            theme=self._theme,
            owner=self,
            pos=(0.0, -0.05),
        )
        ui_list = UIList(
            parent=container.canvas,
            items=items,
            on_select=lambda _index, key: self._launch(key),
            theme=self._theme,
            owner=self,
            pos=(0.0, 0.0),
            item_height=0.06,
            scale=self._theme.body_scale,
        )
        container.set_content(ui_list)

        right_panel = UIPanel(
            parent=parent,
            title="Controls",
            width=0.75,
            height=0.95,
            theme=self._theme,
            owner=self,
            pos=(0.72, 0.0, -0.05),
        )

        if self._last_key is not None:
            last_text = OnscreenText(
                text=f"Last: {self._last_key}",
                pos=(0.0, 0.30),
                scale=self._theme.body_scale,
                fg=(0.7, 0.9, 0.7, 1.0),
                parent=right_panel.content_parent,
                align=0,
            )
            self._texts.append(last_text)

        button_row = UIRow(
            parent=right_panel.content_parent,
            spacing=0.03,
            owner=self,
            pos=(0.0, -0.15),
        )
        button_row.add(
            UIButton(
                parent=button_row.node,
                text="R: Re-run",
                command=self._rerun_last,
                theme=self._theme,
                owner=self,
                scale=0.06,
            )
        )
        button_row.add(
            UIButton(
                parent=button_row.node,
                text="Q: Quit",
                command=self._quit,
                theme=self._theme,
                owner=self,
                scale=0.06,
            )
        )

        hint = OnscreenText(
            text="Keys: digits + Enter, Backspace, R, Q",
            pos=(0.0, -0.35),
            scale=self._theme.body_scale - 0.005,
            fg=(0.6, 0.6, 0.6, 1.0),
            parent=right_panel.content_parent,
            align=0,
        )
        self._texts.append(hint)

        self._status_text = OnscreenText(
            text=status or "Idle.",
            pos=(0.0, -0.92),
            scale=self._theme.body_scale,
            fg=(1.0, 0.9, 0.4, 1.0),
            align=0,
            mayChange=True,
        )
        self._texts.append(self._status_text)
        if self._buffer:
            self._status_text.setText(f"Selection: {self._buffer}")

    def on_start(self) -> None:
        super().on_start()
        self._build_menu("Idle.")
        import builtins

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "accept"):
            for digit in "0123456789":
                base.accept(digit, self._append_digit, [digit])
            base.accept("enter", self._confirm_selection)
            base.accept("return", self._confirm_selection)
            base.accept("backspace", self._backspace)
            base.accept("r", self._rerun_last)
            base.accept("q", self._quit)
        self.add_task("playground_poll", self._poll, pauseable=False)

    def on_stop(self) -> None:
        self.remove_task("playground_poll")
        import builtins

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            for digit in "0123456789":
                base.ignore(digit)
            for key in ("enter", "return", "backspace", "r", "q"):
                base.ignore(key)
        self._clear_ui()
        super().on_stop()

    def _append_digit(self, digit: str) -> None:
        if self._running_key is not None:
            return
        if len(self._buffer) < 2:
            self._buffer += digit
            if self._status_text is not None:
                self._status_text.setText(f"Selection: {self._buffer}")

    def _backspace(self) -> None:
        if self._running_key is not None:
            return
        self._buffer = self._buffer[:-1]
        if self._status_text is not None:
            self._status_text.setText(
                f"Selection: {self._buffer}" if self._buffer else "Idle."
            )

    def _confirm_selection(self) -> None:
        if self._running_key is not None or not self._buffer:
            return
        try:
            index = int(self._buffer) - 1
        except ValueError:
            self._buffer = ""
            return
        self._buffer = ""
        if 0 <= index < len(self._visual_keys):
            self._launch(self._visual_keys[index])

    def _rerun_last(self) -> None:
        if self._running_key is not None:
            return
        if self._last_key is not None and self._last_key in self._visual_keys:
            self._launch(self._last_key)

    def _launch(self, key: str) -> None:
        if self._running_key is not None:
            return
        self._running_key = key
        self._result = None
        self._launch_started = time.monotonic()
        self._build_menu(f"Launching {key}...")
        self._worker = threading.Thread(
            target=self._run_worker, args=(key,), daemon=True
        )
        self._worker.start()

    def _run_worker(self, key: str) -> None:
        exit_code, _output, timed_out, duration = run_scene(key, self.timeout)
        self._result = (key, exit_code, timed_out, duration)

    def _poll(self, task) -> int:
        if self._running_key is not None and self._worker is not None:
            if not self._worker.is_alive():
                self._worker = None
                key = self._running_key
                self._running_key = None
                result = self._result
                if result is not None:
                    _key, exit_code, timed_out, duration = result
                    self._last_key = key
                    if timed_out:
                        status = f"{key}: TIMEOUT ({duration:.1f}s)"
                    elif exit_code == 0:
                        status = f"{key}: OK ({duration:.1f}s)"
                    else:
                        status = f"{key}: FAIL exit={exit_code} ({duration:.1f}s)"
                else:
                    status = f"{key}: finished"
                self._build_menu(status)
            else:
                elapsed = time.monotonic() - self._launch_started
                if self._status_text is not None:
                    self._status_text.setText(
                        f"Running {self._running_key}... {elapsed:.0f}s / {self.timeout}s"
                    )
        return task.cont

    def _quit(self) -> None:
        import builtins

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "userExit"):
            base.userExit()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Panda playground selector")
    parser.add_argument(
        "--list", action="store_true", help="List registered scenes and exit."
    )
    parser.add_argument(
        "--scene", metavar="KEY", help="Run one scene directly and exit."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Subprocess timeout in seconds (default: 120).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.list:
        for key in sorted(SCENE_REGISTRY):
            title, category, scene_cls = SCENE_REGISTRY[key]
            print(f"{key:22} {category:12} {title}  ({scene_cls.__module__})")
        return 0

    if args.scene is not None:
        if args.scene not in SCENE_REGISTRY:
            print(f"Unknown scene: {args.scene}", file=sys.stderr)
            return 2
        exit_code, _output, timed_out, _duration = run_scene(args.scene, args.timeout)
        return 124 if timed_out else exit_code

    app = game.Game()
    playground = Playground(timeout=args.timeout)
    app.add_scene(playground, set_as_main=True)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
