# UI components

Reusable UI primitives for playground and sandboxes. They wrap Panda3D `DirectGui`
widgets behind a small, consistent API and central theme.

## Primitives

- `UITheme`: style tokens (colors, scale, padding).
- `UIComponent`: common base for cleanup and visibility.
- `UIButton`: clickable button with text and command.
- `UIList`: vertical list of selectable items.
- `UIScrollContainer`: scrollable frame hosting content.

## Usage

```python
from src.ui import UIButton, UIList, UIScrollContainer, UITheme

theme = UITheme()
container = UIScrollContainer(parent=base.aspect2d, width=0.6, height=0.8, theme=theme)
button = UIButton(parent=base.aspect2d, text="Run", command=run, theme=theme)
```

## Lifecycle

- Create components in `on_start`, not in `__init__`.
- Always call `destroy()` in `on_stop` or use an owner that tracks them.
- Components are idempotent on repeated `destroy()`.

## Headless compatibility

Components do not create `ShowBase`. Tests bootstrap `ShowBase(windowType="none")`
when needed, as the rest of the terminal suites do.

## Layout containers

- `UIPanel`: framed container with title and padded `content_parent`.
- `UIRow`: horizontal layout with automatic spacing.
- `UIColumn`: vertical layout with automatic spacing.
- `UIGrid`: simple grid layout with fixed columns.

Example:

```python
panel = UIPanel(parent=base.aspect2d, title="Controls", width=0.6, height=0.8)
column = UIColumn(parent=panel.content_parent, spacing=0.02)
for label in ("Pause", "Reset"):
    column.add(UIButton(parent=column.node, text=label))
```

Source: `src/ui/`
Tests: `tests/terminal/ui_components_test.py`, `tests/terminal/ui_layout_test.py`
