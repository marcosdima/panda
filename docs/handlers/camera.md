# Camera Handlers

Camera handlers read where the entity is and write to the camera node. They never move the entity.

Both cameras split their work across the two frame phases: **look** happens before the physics step, **transform** happens after it. The rule and the reasoning are in [../engine/update_pipeline.md](../engine/update_pipeline.md).

## `FirstPersonCameraHandler`

`src/handlers/camera/first_person.py` locks the camera to the eye of the character.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `eye_offset` | `(0, 0, 1.5)` | Offset from the body pivot to the eye. |
| `yaw` / `pitch` | `0.0` | Initial orientation. |
| `min_pitch` / `max_pitch` | `-89` / `89` | Vertical clamp in degrees. |
| `mouse_sensitivity` | `0.2` | Degrees per mouse unit. |
| `invert_yaw` / `invert_pitch` | `False` | Invert the mouse axes. |
| `collision_enabled` | `True` | Resolve the eye against the geometry. |
| `collision_margin` | `0.2` | Radius of the sphere swept from the pivot to the eye. |
| `hide_self` | `True` | Hide the character mesh in first person. |
| `near_plane` / `far_plane` | `0.1` / `1000.0` | Applied to the real lens. |
| `smooth_factor` | `0.0` | Position smoothing in `[0, 1]`, applied before collision resolution. |
| `pivot_offset` | `None` | Offset of the body pivot inside the capsule. |

Behaviour:

- **See-through protection.** The eye is resolved with a single *sphere sweep* from a pivot inside the character to the desired eye, so walls, corners, floors and ceilings are handled uniformly. The sphere radius is capped to 90% of the capsule radius, and the near plane is reduced so the whole near-plane rectangle always fits inside it: the view can never show geometry the eye is touching.
- The near plane is applied to the **real lens** (`base.cam` / `base.camLens`), not to the `base.camera` transform node, and the original values are restored on stop.
- Position smoothing runs *before* collision resolution; the look direction is never smoothed.
- **Pointer capture** follows `Tab` / `Escape` / `mouse1`. `set_pointer_captured(False)` releases it.
- **Headless safe:** tests drive `handle_mouse_delta(dx, dy)` directly with the capture disabled, so no window is needed.
- `get_forward_vector()`, `get_body_yaw()`, `get_pivot_pos()` and `get_eye_pos()` stay available in the pre-physics phase, which is what movement code uses to orient relative to the camera.

## `ThirdPersonCameraHandler`

`src/handlers/camera/third_person.py` orbits around the entity.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `distance` | `8.0` | Initial orbit distance, clamped to the range. |
| `min_distance` / `max_distance` | `2.0` / `25.0` | Zoom limits. |
| `target_offset` | `(0, 0, 1.5)` | Pivot offset above the entity. |
| `pitch` | `-15.0` | Initial vertical angle, clamped to `min_pitch`/`max_pitch`. |
| `yaw` | `0.0` | Initial horizontal angle. |
| `smooth_speed` | `10.0` | Follow speed. |
| `zoom_step` / `zoom_speed` | `1.0` / `10.0` | Zoom amount per step and how fast it converges. |
| `collision_enabled` | `True` | Pull the camera in when geometry blocks it. |
| `collision_margin` | `0.3` | Margin kept from the blocked surface. |
| `shoulder_offset` | `(0, 0, 0)` | Horizontal offset of the orbit pivot. |
| `owner_min_distance` | `1.0` | Minimum distance to the owner. |
| `preset` | `None` | A `CameraPreset` or its name, applied on start. |

Behaviour:

- `distance` and `target_distance` are the current and the requested distance; `zoom(delta)`, `zoom_in()` and `zoom_out()` move between them.
- `compute_ideal_position()` and `resolve_collision_position()` expose the two steps of the placement, which is what makes the behaviour testable.
- `snap_to_target()` places the camera immediately, without smoothing.
- `apply_preset(preset, snap=True)` applies a preset by object or by name.

## Camera presets

`src/handlers/camera/presets.py` holds the standard third-person perspectives as immutable `CameraPreset` values:

| Preset | Distance | Pitch | Character |
| --- | --- | --- | --- |
| `ADVENTURE_PRESET` | 7.5 | -15° | Orbit, centred behind the character. Action, RPG and platformers. |
| `SHOOTER_PRESET` | 3.2 | -10° | Over the shoulder, offset to the right. Third-person shooters. |
| `ISOMETRIC_PRESET` | 14.0 | -45° | Angled overhead. Strategy and ARPG. |
| `OVERHEAD_PRESET` | 16.0 | -85° | Top-down. Tactical and grid games. |

`PRESETS_BY_NAME` resolves a preset from several spellings (`"shooter"`, `"shoulder"`, `"tps"`, `"iso"`, `"top_down"`), and `PresetName` holds the canonical names. Presets exist for the third-person camera only.

## Collision masks

Both cameras query the world with the `CameraCollision` mask, which shares its blocker bit with `LineOfSight`. Character capsules and trigger volumes clear that bit, so they never block the camera, while world geometry blocks it. The convention is documented in [../engine/physics_world.md](../engine/physics_world.md).

Source: `src/handlers/camera/`
Tests: `tests/terminal/camera_handler.py`, `tests/terminal/post_update_test.py`
