from __future__ import annotations

import builtins
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from panda3d.core import WindowProperties

from src.scenes import Scene


@dataclass
class InspectorField:
    """Descriptor for a live-editable field or action in the sandbox pause inspector."""

    label: str
    kind: str  # "numeric", "bool", "action"
    getter: Callable[[], Any]
    setter: Callable[[Any], None]
    min_val: float = 0.0
    max_val: float = 20.0
    step: float = 0.5
    key: tuple[int, str] | None = None

    def get(self) -> Any:
        return self.getter()

    def set(self, value: Any) -> Any:
        if self.kind == "numeric":
            clamped = max(self.min_val, min(self.max_val, float(value)))
            self.setter(clamped)
            return clamped
        if self.kind == "bool":
            bval = bool(value)
            self.setter(bval)
            return bval
        if self.kind == "action":
            self.setter(None)
            return None
        self.setter(value)
        return value

    def step_by(self, steps: int = 1) -> Any:
        if self.kind == "numeric":
            curr = float(self.get())
            return self.set(round(curr + self.step * steps, 6))
        if self.kind == "bool":
            return self.set(not bool(self.get()))
        if self.kind == "action":
            return self.set(None)
        return self.get()


class Test(Scene):
    __test__ = False  # not a pytest test class

    _ROWS_PER_PAGE: int = 8

    def __init__(self) -> None:
        super().__init__()
        self._inspector_fields: list[InspectorField] = []
        self._inspector_keys: set[tuple[int, str]] = set()
        self._inspector_discovered: bool = False
        self._sandbox_paused: bool = False
        self._inspector_frame: Any = None
        self._inspector_page: int = 0
        self._updating_inspector_ui: bool = False
        self.auto_discover_inspector_fields: bool = True
        self._replay_mode: str | None = None
        self._replay_path: str | None = None
        self._replay_duration: float = 0.0
        self._replay_elapsed: float = 0.0
        self._replay_recorder: Any = None
        self._replay_player: Any = None
        self._replay_exit_code: int = 0

    # ------------------------------------------------------------------
    # Replay helpers
    # ------------------------------------------------------------------
    def enable_replay_record(self, path: str, duration: float = 5.0, fixed_dt: float = 0.016) -> None:
        from src.utils.replay import ReplayRecorder

        self._replay_mode = "record"
        self._replay_path = path
        self._replay_duration = float(duration)
        self._replay_recorder = ReplayRecorder(self, fixed_dt=fixed_dt)
        self._replay_scene_name = type(self).__name__

    def enable_replay_replay(self, path: str, duration: float = 5.0) -> None:
        from src.utils.replay import ReplayPlayer

        self._replay_mode = "replay"
        self._replay_path = path
        self._replay_player = ReplayPlayer(path)
        self._replay_duration = float(duration)
        self._replay_exit_code = 0

    def record_replay_event(self, event_type: str, **payload) -> None:
        recorder = self._replay_recorder
        if recorder is not None:
            recorder.record_event(event_type, **payload)

    def capture_replay_state(self) -> dict:
        return {}

    def apply_replay_event(self, event: dict) -> None:
        return None

    def finalize_replay(self) -> list[str]:
        errors: list[str] = []
        if self._replay_mode == "record" and self._replay_recorder is not None and self._replay_path is not None:
            snapshots = self._replay_recorder.snapshots
            if not snapshots or abs(float(snapshots[-1].get("t", -1.0)) - self._replay_elapsed) > 1e-6:
                self._replay_recorder.record_snapshot(self._replay_elapsed, self.capture_replay_state())
            self._replay_recorder.add_assertion("end", "_replay_phase", getattr(self, "_replay_phase", None))
            self._replay_recorder.save(self._replay_path)
            self.p(f"Replay recorded: {self._replay_path}", color="green")
        elif self._replay_mode == "replay" and self._replay_player is not None:
            errors = self._replay_player.finalize(self)
            if errors:
                self._replay_exit_code = 1
                for error in errors:
                    self.p(f"Replay mismatch: {error}", color="red")
            else:
                self.p("Replay OK", color="green")
        return errors

    @property
    def is_sandbox_paused(self) -> bool:
        """Return True while the sandbox pause inspector is open."""
        return self._sandbox_paused

    # ------------------------------------------------------------------
    # Inspector field registration API
    # ------------------------------------------------------------------

    def expose_field(
        self,
        label: str,
        target: Any,
        attr: str,
        min_val: float = 0.0,
        max_val: float = 20.0,
        step: float = 0.5,
        on_change: Callable[[Any], None] | None = None,
    ) -> InspectorField:
        """Expose an attribute (or dict key) on ``target`` for live editing when paused."""
        key = (id(target), attr)
        is_dict = isinstance(target, dict)
        initial = target.get(attr) if is_dict else getattr(target, attr, 0.0)
        kind = "bool" if isinstance(initial, bool) else "numeric"

        def _getter() -> Any:
            return target[attr] if is_dict else getattr(target, attr)

        def _setter(val: Any) -> None:
            if is_dict:
                target[attr] = val
            else:
                setattr(target, attr, val)
            if on_change is not None:
                on_change(val)

        field = InspectorField(
            label=label,
            kind=kind,
            getter=_getter,
            setter=_setter,
            min_val=float(min_val),
            max_val=float(max_val),
            step=float(step),
            key=key,
        )
        self._register_inspector_field(field)
        return field

    def expose_property(
        self,
        label: str,
        getter: Callable[[], float],
        setter: Callable[[float], None],
        min_val: float = 0.0,
        max_val: float = 20.0,
        step: float = 0.5,
    ) -> InspectorField:
        """Expose a custom numeric getter/setter pair in the sandbox pause inspector."""
        field = InspectorField(
            label=label,
            kind="numeric",
            getter=getter,
            setter=setter,
            min_val=float(min_val),
            max_val=float(max_val),
            step=float(step),
        )
        self._register_inspector_field(field)
        return field

    def expose_toggle(
        self,
        label: str,
        getter: Callable[[], bool],
        setter: Callable[[bool], None],
    ) -> InspectorField:
        """Expose a boolean toggle in the sandbox pause inspector."""
        field = InspectorField(
            label=label,
            kind="bool",
            getter=getter,
            setter=setter,
        )
        self._register_inspector_field(field)
        return field

    def expose_action(
        self,
        label: str,
        callback: Callable[[], None],
    ) -> InspectorField:
        """Expose a clickable action button in the sandbox pause inspector."""
        field = InspectorField(
            label=label,
            kind="action",
            getter=lambda: None,
            setter=lambda _v: callback(),
        )
        self._register_inspector_field(field)
        return field

    def _register_inspector_field(self, field: InspectorField) -> None:
        if field.key is not None:
            if field.key in self._inspector_keys:
                return
            self._inspector_keys.add(field.key)
        self._inspector_fields.append(field)

    def get_inspector_fields(self) -> list[InspectorField]:
        """Return all registered and auto-discovered inspector fields."""
        if self.auto_discover_inspector_fields and not self._inspector_discovered:
            self._auto_discover_fields()
        return list(self._inspector_fields)

    def set_field_value(self, label_or_index: str | int, value: Any) -> Any:
        """Programmatically set an inspector field's value by label or index."""
        field = self._find_field(label_or_index)
        result = field.set(value)
        if self._inspector_frame is not None:
            self._rebuild_inspector_ui()
        return result

    def step_field_value(self, label_or_index: str | int, delta_steps: int = 1) -> Any:
        """Programmatically increment/decrement (or toggle) an inspector field by label or index."""
        field = self._find_field(label_or_index)
        result = field.step_by(delta_steps)
        if self._inspector_frame is not None:
            self._rebuild_inspector_ui()
        return result

    def _find_field(self, label_or_index: str | int) -> InspectorField:
        fields = self.get_inspector_fields()
        if isinstance(label_or_index, int):
            return fields[label_or_index]
        for field in fields:
            if field.label == label_or_index:
                return field
        raise KeyError(f"Inspector field not found: {label_or_index!r}")

    def _auto_discover_fields(self) -> None:
        """Discover standard tunable attributes on handlers attached to scene entities."""
        self._inspector_discovered = True
        specs_by_class: dict[str, list[tuple[str, str, float, float, float]]] = {
            "CharacterControllerHandler": [
                ("walk_speed", "Walk Speed", 1.0, 20.0, 0.5),
                ("sprint_speed", "Sprint Speed", 2.0, 30.0, 0.5),
                ("jump_speed", "Jump Speed", 1.0, 20.0, 0.5),
                ("gravity", "Gravity", 1.0, 40.0, 1.0),
                ("turn_speed", "Turn Speed", 0.0, 30.0, 1.0),
                ("acceleration", "Acceleration", 0.0, 50.0, 2.5),
            ],
            "ThirdPersonCameraHandler": [
                ("distance", "Cam Distance", 1.5, 25.0, 0.5),
                ("pitch", "Cam Pitch", -75.0, 45.0, 2.5),
                ("smooth_speed", "Cam Smooth", 0.0, 25.0, 1.0),
                ("mouse_sensitivity", "Mouse Sens", 0.05, 1.0, 0.05),
            ],
            "FirstPersonCameraHandler": [
                ("mouse_sensitivity", "FP Mouse Sens", 0.05, 1.0, 0.05),
                ("collision_margin", "FP Col Margin", 0.02, 1.0, 0.02),
                ("smooth_factor", "FP Smooth", 0.0, 0.95, 0.05),
            ],
            "AIPatrolHandler": [
                ("sight_range", "AI Sight Range", 1.0, 25.0, 0.5),
                ("lose_range", "AI Lose Range", 2.0, 35.0, 0.5),
                ("arrive_radius", "AI Arrive Rad", 0.2, 5.0, 0.2),
                ("wait_time", "AI Wait Time", 0.0, 5.0, 0.25),
                ("chase_sprint", "AI Chase Sprint", 0.0, 1.0, 1.0),
            ],
            "FollowHandler": [
                ("stop_radius", "Follow Stop Rad", 0.5, 10.0, 0.25),
                ("speed_factor", "Follow Speed Fac", 0.2, 2.5, 0.1),
                ("chase_sprint", "Follow Sprint", 0.0, 1.0, 1.0),
            ],
            "ProximitySensorHandler": [
                ("radius", "Enter Radius", 0.5, 15.0, 0.5),
                ("exit_radius", "Exit Radius", 1.0, 20.0, 0.5),
            ],
            "ActorAnimationHandler": [
                ("blend_duration", "Anim Blend (s)", 0.0, 0.8, 0.02),
                ("air_threshold", "Air Threshold", 0.0, 0.5, 0.02),
                ("blend_easing", "Blend Easing", 0.0, 1.0, 1.0),
            ],
        }

        from src.handlers.base import Handler

        multi_entity = len(self.entities) > 2
        for entity in list(self.entities.values()):
            prefix = f"{entity.name}: " if multi_entity else ""
            for handler in entity.get_handlers(Handler):
                cls_name = type(handler).__name__
                for attr, label, min_v, max_v, step in specs_by_class.get(cls_name, ()):
                    if hasattr(handler, attr):
                        self.expose_field(
                            label=f"{prefix}{label}",
                            target=handler,
                            attr=attr,
                            min_val=min_v,
                            max_val=max_v,
                            step=step,
                        )

    # ------------------------------------------------------------------
    # Pause & Live Inspector Lifecycle
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        super().on_start()
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base is not None else None
        if base is not None and win is not None and hasattr(base, "accept"):
            base.accept("escape", self.toggle_sandbox_pause)
            base.accept("p", self.toggle_sandbox_pause)

    def on_stop(self) -> None:
        if self._sandbox_paused:
            self.set_sandbox_paused(False)
        self._destroy_inspector_ui()
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "ignore"):
            base.ignore("escape")
            base.ignore("p")
        self._inspector_fields.clear()
        self._inspector_keys.clear()
        self._inspector_discovered = False
        super().on_stop()

    def toggle_sandbox_pause(self) -> bool:
        """Toggle pause mode and open/close the live sandbox inspector overlay."""
        return self.set_sandbox_paused(not self._sandbox_paused)

    def set_sandbox_paused(self, paused: bool) -> bool:
        """Set sandbox pause state, sync Game & Physics, and show/hide the inspector UI."""
        self._sandbox_paused = bool(paused)
        from src.globals.physics import Physics
        from src.utils import bus

        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "set_paused"):
            base.set_paused(self._sandbox_paused)
        else:
            if base is not None:
                base.paused = self._sandbox_paused
            Physics.set_paused(self._sandbox_paused)
            bus.publish("game_paused", self._sandbox_paused)

        win = getattr(base, "win", None) if base is not None else None
        if self._sandbox_paused:
            if win is not None and hasattr(win, "requestProperties"):
                props = WindowProperties()
                props.setCursorHidden(False)
                props.setMouseMode(WindowProperties.M_absolute)
                win.requestProperties(props)
            self._build_inspector_ui()
        else:
            self._destroy_inspector_ui()
        return self._sandbox_paused

    # ------------------------------------------------------------------
    # DirectGui Inspector Rendering (graphical mode only)
    # ------------------------------------------------------------------

    def _build_inspector_ui(self) -> None:
        """Build the interactive pause inspector overlay when a graphics window is active."""
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base is not None else None
        if base is None or win is None:
            return
        self._rebuild_inspector_ui()

    def _destroy_inspector_ui(self) -> None:
        """Destroy the DirectGui pause inspector overlay if present."""
        if self._inspector_frame is not None:
            try:
                self._inspector_frame.destroy()
            except Exception:  # noqa: BLE001, S110
                pass
            self._inspector_frame = None

    def _rebuild_inspector_ui(self) -> None:
        """Rebuild the current page of the pause inspector overlay."""
        self._destroy_inspector_ui()
        base = getattr(builtins, "base", None)
        win = getattr(base, "win", None) if base is not None else None
        if base is None or win is None:
            return

        try:
            from direct.gui.DirectGui import (
                DirectButton,
                DirectFrame,
                DirectLabel,
                DirectSlider,
            )
            from panda3d.core import TextNode
        except Exception:  # noqa: BLE001
            return

        fields = self.get_inspector_fields()
        total_pages = max(1, (len(fields) + self._ROWS_PER_PAGE - 1) // self._ROWS_PER_PAGE)
        self._inspector_page = max(0, min(self._inspector_page, total_pages - 1))
        start_idx = self._inspector_page * self._ROWS_PER_PAGE
        page_fields = fields[start_idx : start_idx + self._ROWS_PER_PAGE]

        self._updating_inspector_ui = True
        try:
            panel = DirectFrame(
                frameColor=(0.06, 0.08, 0.11, 0.90),
                frameSize=(-0.82, 0.82, -0.76, 0.78),
                pos=(0.0, 0.0, 0.0),
            )
            self._inspector_frame = panel

            DirectLabel(
                parent=panel,
                text="PAUSED — LIVE SANDBOX INSPECTOR",
                scale=0.052,
                pos=(0.0, 0.0, 0.68),
                text_fg=(0.25, 0.90, 1.0, 1.0),
                frameColor=(0, 0, 0, 0),
            )
            DirectLabel(
                parent=panel,
                text="Edit fields live while paused | Press [Esc] or [P] to Resume",
                scale=0.035,
                pos=(0.0, 0.0, 0.61),
                text_fg=(0.80, 0.85, 0.90, 1.0),
                frameColor=(0, 0, 0, 0),
            )

            if not page_fields:
                DirectLabel(
                    parent=panel,
                    text="No tunable fields registered for this scene.",
                    scale=0.042,
                    pos=(0.0, 0.0, 0.10),
                    text_fg=(0.75, 0.75, 0.75, 1.0),
                    frameColor=(0, 0, 0, 0),
                )

            for row_i, field in enumerate(page_fields):
                z = 0.48 - row_i * 0.125
                DirectLabel(
                    parent=panel,
                    text=field.label,
                    scale=0.038,
                    pos=(-0.76, 0.0, z - 0.01),
                    text_align=TextNode.ALeft,
                    text_fg=(0.95, 0.95, 0.95, 1.0),
                    frameColor=(0, 0, 0, 0),
                )

                if field.kind == "numeric":
                    curr_val = float(field.get())
                    val_label = DirectLabel(
                        parent=panel,
                        text=f"{curr_val:.2f}",
                        scale=0.038,
                        pos=(0.66, 0.0, z - 0.01),
                        text_align=TextNode.ACenter,
                        text_fg=(0.3, 0.95, 0.55, 1.0),
                        frameColor=(0, 0, 0, 0),
                    )

                    slider_holder: list[Any] = [None]

                    def _on_slider(
                        f: InspectorField = field,
                        lbl: Any = val_label,
                        sh: list[Any] = slider_holder,
                    ) -> None:
                        if self._updating_inspector_ui or sh[0] is None:
                            return
                        raw = float(sh[0]["value"])
                        if f.step > 0.0:
                            steps = round((raw - f.min_val) / f.step)
                            snapped = f.min_val + steps * f.step
                        else:
                            snapped = raw
                        new_v = f.set(round(snapped, 5))
                        lbl["text"] = f"{float(new_v):.2f}"

                    slider = DirectSlider(
                        parent=panel,
                        range=(field.min_val, max(field.max_val, field.min_val + 1e-4)),
                        value=max(field.min_val, min(field.max_val, curr_val)),
                        pageSize=field.step if field.step > 0 else 0.1,
                        scale=0.26,
                        pos=(0.14, 0.0, z),
                        frameColor=(0.18, 0.22, 0.28, 1.0),
                        thumb_frameColor=(0.25, 0.75, 0.95, 1.0),
                        command=_on_slider,
                    )
                    slider_holder[0] = slider

                    def _step_btn(
                        delta: int,
                        f: InspectorField = field,
                        lbl: Any = val_label,
                        sh: list[Any] = slider_holder,
                    ) -> None:
                        new_v = float(f.step_by(delta))
                        lbl["text"] = f"{new_v:.2f}"
                        if sh[0] is not None:
                            self._updating_inspector_ui = True
                            try:
                                sh[0]["value"] = max(f.min_val, min(f.max_val, new_v))
                            finally:
                                self._updating_inspector_ui = False

                    DirectButton(
                        parent=panel,
                        text="-",
                        scale=0.042,
                        pos=(-0.18, 0.0, z - 0.01),
                        frameSize=(-0.7, 0.7, -0.45, 0.65),
                        frameColor=(0.22, 0.25, 0.32, 1.0),
                        text_fg=(1, 1, 1, 1),
                        command=_step_btn,
                        extraArgs=[-1],
                    )
                    DirectButton(
                        parent=panel,
                        text="+",
                        scale=0.042,
                        pos=(0.46, 0.0, z - 0.01),
                        frameSize=(-0.7, 0.7, -0.45, 0.65),
                        frameColor=(0.22, 0.25, 0.32, 1.0),
                        text_fg=(1, 1, 1, 1),
                        command=_step_btn,
                        extraArgs=[1],
                    )

                elif field.kind == "bool":
                    state = bool(field.get())
                    btn_holder: list[Any] = [None]

                    def _toggle_bool(f: InspectorField = field, bh: list[Any] = btn_holder) -> None:
                        new_state = bool(f.step_by(1))
                        if bh[0] is not None:
                            bh[0]["text"] = "ON" if new_state else "OFF"
                            bh[0]["frameColor"] = (0.18, 0.62, 0.34, 1.0) if new_state else (0.45, 0.20, 0.22, 1.0)

                    tbtn = DirectButton(
                        parent=panel,
                        text="ON" if state else "OFF",
                        scale=0.040,
                        pos=(0.14, 0.0, z - 0.01),
                        frameSize=(-2.4, 2.4, -0.45, 0.65),
                        frameColor=(0.18, 0.62, 0.34, 1.0) if state else (0.45, 0.20, 0.22, 1.0),
                        text_fg=(1, 1, 1, 1),
                        command=_toggle_bool,
                    )
                    btn_holder[0] = tbtn

                elif field.kind == "action":

                    def _run_action(f: InspectorField = field) -> None:
                        f.set(None)
                        if self._sandbox_paused:
                            self._rebuild_inspector_ui()

                    DirectButton(
                        parent=panel,
                        text="Run",
                        scale=0.040,
                        pos=(0.14, 0.0, z - 0.01),
                        frameSize=(-2.4, 2.4, -0.45, 0.65),
                        frameColor=(0.22, 0.45, 0.72, 1.0),
                        text_fg=(1, 1, 1, 1),
                        command=_run_action,
                    )

            # Pagination controls if more than 1 page
            if total_pages > 1:
                DirectButton(
                    parent=panel,
                    text="< Prev",
                    scale=0.038,
                    pos=(-0.30, 0.0, -0.54),
                    frameSize=(-1.8, 1.8, -0.45, 0.65),
                    frameColor=(0.20, 0.24, 0.30, 1.0),
                    text_fg=(1, 1, 1, 1),
                    command=self._change_inspector_page,
                    extraArgs=[-1],
                )
                DirectLabel(
                    parent=panel,
                    text=f"Page {self._inspector_page + 1} / {total_pages}",
                    scale=0.036,
                    pos=(0.0, 0.0, -0.55),
                    text_fg=(0.85, 0.85, 0.85, 1.0),
                    frameColor=(0, 0, 0, 0),
                )
                DirectButton(
                    parent=panel,
                    text="Next >",
                    scale=0.038,
                    pos=(0.30, 0.0, -0.54),
                    frameSize=(-1.8, 1.8, -0.45, 0.65),
                    frameColor=(0.20, 0.24, 0.30, 1.0),
                    text_fg=(1, 1, 1, 1),
                    command=self._change_inspector_page,
                    extraArgs=[1],
                )

            # Bottom toolbar: Resume | Wireframe | Quit
            DirectButton(
                parent=panel,
                text="Resume (Esc)",
                scale=0.042,
                pos=(-0.42, 0.0, -0.67),
                frameSize=(-3.2, 3.2, -0.5, 0.7),
                frameColor=(0.18, 0.58, 0.34, 1.0),
                text_fg=(1, 1, 1, 1),
                command=lambda: self.set_sandbox_paused(False),
            )
            DirectButton(
                parent=panel,
                text="Wireframe (F12)",
                scale=0.042,
                pos=(0.0, 0.0, -0.67),
                frameSize=(-3.4, 3.4, -0.5, 0.7),
                frameColor=(0.24, 0.36, 0.54, 1.0),
                text_fg=(1, 1, 1, 1),
                command=self._toggle_inspector_wireframe,
            )
            DirectButton(
                parent=panel,
                text="Quit",
                scale=0.042,
                pos=(0.42, 0.0, -0.67),
                frameSize=(-2.4, 2.4, -0.5, 0.7),
                frameColor=(0.62, 0.20, 0.22, 1.0),
                text_fg=(1, 1, 1, 1),
                command=self._quit_from_inspector,
            )
        finally:
            self._updating_inspector_ui = False

    def _change_inspector_page(self, delta: int) -> None:
        self._inspector_page += delta
        self._rebuild_inspector_ui()

    def _toggle_inspector_wireframe(self) -> None:
        from src.globals.physics import Physics

        Physics.toggle_debug()

    def _quit_from_inspector(self) -> None:
        base = getattr(builtins, "base", None)
        if base is not None and hasattr(base, "userExit"):
            base.userExit()

    # ------------------------------------------------------------------
    # Console formatting helpers
    # ------------------------------------------------------------------

    def p(
        self,
        msg: str,
        *,
        bold: bool = False,
        color: str | None = None,
        center: bool = False,
        width: int = 40,
        raw: bool = False,
    ) -> None:
        """Print a message with optional ANSI formatting.

        - `bold`: bold text
        - `color`: one of black, red, green, yellow, blue, magenta, cyan, white
        - `center`: center text within `width`
        - `raw`: print exactly `msg` without formatting
        - `width`: width for centering (default 40)
        """
        if raw:
            print(msg)
            return

        colors = {
            "black": "\033[30m",
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
            "cyan": "\033[36m",
            "white": "\033[37m",
        }
        bold_code = "\033[1m" if bold else ""
        color_code = colors.get(color.lower(), "") if color else ""
        reset = "\033[0m" if (bold_code or color_code) else ""

        out = msg
        if center:
            out = out.center(width)

        print(f"{bold_code}{color_code}{out}{reset}")

    def space_line(self, length: int = 40) -> None:
        self.p("\n*" + "-" * length + "*\n", color="yellow")

    def print_title(self, title: str = "TESTS", color: str | None = None, width: int = 40) -> None:
        """Print a decorated title using the `p` helper for formatting."""
        self.space_line(width)
        self.p(title, bold=True, color=color, center=True, width=width)
        self.space_line(width)

    def print_subtitle(self, subtitle: str, color: str | None = None, width: int = 40) -> None:
        """Print a decorated subtitle using the `p` helper for formatting."""
        self.p(subtitle, bold=True, color=color, center=True, width=width)
        self.p("-" * width, color=color)
