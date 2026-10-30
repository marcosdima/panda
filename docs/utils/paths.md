# paths (`src/utils/paths.py`)

- `get_project_root(start_path=None)`: walks up from `start_path` (default: the module directory) to the first folder containing `.git` or `pyproject.toml`; falls back to two levels above the module directory.
- `resolve_asset_path(*paths)`: absolute path under `<root>/assets`; raises `ValueError` if `..` or an absolute component escapes the assets directory.

```python
from src.utils import resolve_asset_path

resolve_asset_path("models", "panda.glb")
```

Source: `src/utils/paths.py`
Tests: `tests/terminal/paths_test.py`.
