import importlib
from pathlib import Path

import pytest

# Import the module so we can monkeypatch its __file__ attribute
paths = importlib.import_module("src.utils.paths")


def test_get_project_root_contains_git_or_pyproject(tmp_path, monkeypatch):
    # Simulate a repo structure with a .git folder at the root
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    # Deep nested directory where the module would appear to live
    deep_dir = repo_root / "sub" / "deep"
    deep_dir.mkdir(parents=True)
    dummy_file = deep_dir / "dummy.py"
    dummy_file.touch()
    # Patch the module's __file__ attribute
    monkeypatch.setattr(paths, "__file__", str(dummy_file))
    root = paths.get_project_root()
    assert root == repo_root


def test_resolve_asset_path(tmp_path, monkeypatch):
    # Create a fake project root containing an assets folder
    repo_root = tmp_path / "repo2"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    assets_dir = repo_root / "assets"
    assets_dir.mkdir(parents=True)
    # Place a dummy paths.py file inside the project structure
    dummy_paths = repo_root / "src" / "utils" / "paths.py"
    dummy_paths.parent.mkdir(parents=True, exist_ok=True)
    dummy_paths.touch()
    monkeypatch.setattr(paths, "__file__", str(dummy_paths))
    # Resolve an asset relative to the assets directory
    result = paths.resolve_asset_path("img.png")
    assert result == assets_dir / "img.png"


def test_root_from_start_path_pyproject(tmp_path):
    (tmp_path / "pyproject.toml").touch()
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    assert paths.get_project_root(deep) == tmp_path.resolve()


def test_root_fallback_two_levels_up(tmp_path, monkeypatch):
    dummy = tmp_path / "src" / "utils" / "paths.py"
    dummy.parent.mkdir(parents=True)
    dummy.touch()
    monkeypatch.setattr(paths, "__file__", str(dummy))
    # start_path outside any marker: falls back to <tmp>/ (parent of src)
    isolated = tmp_path / "x"
    isolated.mkdir()
    if not any(
        (p / ".git").is_dir() or (p / "pyproject.toml").is_file()
        for p in [isolated.resolve(), *isolated.resolve().parents]
    ):
        assert paths.get_project_root(isolated) == tmp_path.resolve()


def test_resolve_multi_segment_and_pathlike(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    (tmp_path / "assets").mkdir()
    dummy = tmp_path / "src" / "utils" / "paths.py"
    dummy.parent.mkdir(parents=True)
    dummy.touch()
    monkeypatch.setattr(paths, "__file__", str(dummy))
    expected = tmp_path.resolve() / "assets" / "models" / "a.glb"
    assert paths.resolve_asset_path("models", "a.glb") == expected
    assert paths.resolve_asset_path(Path("models"), Path("a.glb")) == expected
    with pytest.raises(ValueError):
        paths.resolve_asset_path("..", "secret")
    with pytest.raises(ValueError):
        paths.resolve_asset_path("/etc/passwd")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__]))
