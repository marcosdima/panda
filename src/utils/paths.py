"""Filesystem path resolution utilities.

These helpers centralise the logic for locating the project root directory and
building absolute paths to assets or configuration files. They are deliberately
lightweight and rely only on the Python standard library.
"""

from __future__ import annotations

import os
from pathlib import Path

PathLike = str | os.PathLike


def get_project_root(start_path: PathLike | None = None) -> Path:
    """Return the absolute path to the repository root.

    The function walks upwards from *start_path* (default: the directory
    containing this file) until it finds a directory that contains a ``.git``
    folder *or* a ``pyproject.toml`` file. If neither is found it falls back to
    the parent of the ``src`` directory (two levels above this file's folder).
    """

    if start_path is None:
        current = Path(__file__).resolve().parent
    else:
        current = Path(start_path).resolve()
    for parent in [current] + list(current.parents):
        if (parent / ".git").is_dir() or (parent / "pyproject.toml").is_file():
            return parent
    # Fallback - two levels up from src/utils (the repo root layout)
    return Path(__file__).resolve().parent.parent.parent


def resolve_asset_path(*paths: PathLike) -> Path:
    """Build an absolute path to an asset located under the project ``assets``
    directory.

    Parameters
    ----------
    *paths:
        Relative path components that will be joined after the ``assets``
        directory. Elements may be strings or ``Path``‑like objects.

    Returns
    -------
    pathlib.Path
        An absolute path pointing to ``<project_root>/assets/<joined paths>``.

    Raises
    ------
    ValueError
        If the joined path escapes the assets directory (``..`` segments or
        an absolute component).
    """

    asset_dir = (get_project_root() / "assets").resolve()
    resolved = asset_dir.joinpath(*paths).resolve()
    if not resolved.is_relative_to(asset_dir):
        raise ValueError(f"path escapes the assets directory: {resolved}")
    return resolved
