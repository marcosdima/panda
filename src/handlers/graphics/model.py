from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from panda3d.core import NodePath, Vec3

from config import ASSETS_PATH
from src.globals.loader import GlobalLoader
from src.handlers.base import Handler

if TYPE_CHECKING:
    from src.entities.entity import Entity


logger = logging.getLogger(__name__)


class ModelHandler(Handler):
    """Static geometry handler that loads a model asset and reparents it onto the entity.

    The model template is resolved through `GlobalLoader` (cached) and a deep
    `copyTo` instance is reparented under `entity.node` on attach/start, so
    multiple entities can share one cached template without stealing each
    other's nodes. Supports `.bam` / `.glb` / `.egg` assets and applies
    `scale`, `offset`, and `hpr` transforms. Cleanup removes the instance
    node on stop/detach without touching the shared template.
    """

    def __init__(
        self,
        model_path: str,
        scale: float = 1.0,
        offset: Vec3 = Vec3(0.0, 0.0, 0.0),
        hpr: Vec3 = Vec3(0.0, 0.0, 0.0),
        from_assets: bool = True,
    ) -> None:
        super().__init__()
        self.model_path: str = model_path
        self.scale: float = float(scale)
        self.offset: Vec3 = Vec3(offset)
        self.hpr: Vec3 = Vec3(hpr)
        self.from_assets: bool = from_assets

        self.model_np: NodePath | None = None

    def _resolve_path(self) -> str:
        """Resolve the model path to a full asset path (ASSETS_PATH-prefixed or absolute)."""
        if (
            not self.from_assets
            or self.model_path.startswith("/")
            or self.model_path.startswith(ASSETS_PATH)
        ):
            return self.model_path
        return ASSETS_PATH + self.model_path

    def _load_template(self) -> NodePath | None:
        """Load or fetch the cached model template, returning None when loading fails."""
        full_path = self._resolve_path()
        try:
            template = GlobalLoader.load(full_path)
        except (IOError, OSError):
            logger.warning("Failed to load model '%s'.", full_path, exc_info=True)
            return None
        if template is None or template.isEmpty():
            logger.warning("Model '%s' resolved to an empty NodePath.", full_path)
            return None
        return template

    def _setup_nodes(self) -> None:
        """Create the model instance under entity.node and apply configured transforms."""
        if self.entity is None:
            return

        if self.model_np is not None and not self.model_np.isEmpty():
            if self.model_np.getParent() != self.entity.node:
                self.model_np.reparentTo(self.entity.node)
            return

        template = self._load_template()
        if template is None:
            self.model_np = NodePath("ModelFallback")
            self.model_np.reparentTo(self.entity.node)
            return

        self.model_np = template.copyTo(self.entity.node)
        self.model_np.setScale(self.scale)
        self.model_np.setPos(self.offset)
        self.model_np.setHpr(self.hpr)

    def _cleanup_nodes(self) -> None:
        """Remove the model instance node while preserving the cached template."""
        if self.model_np is not None and not self.model_np.isEmpty():
            self.model_np.removeNode()
        self.model_np = None

    def on_attach(self, entity: Entity) -> None:
        """Attach handler to entity and load the model instance."""
        super().on_attach(entity)
        self._setup_nodes()

    def on_start(self) -> None:
        """Called when the active scene or entity starts; rebuilds the model if missing."""
        super().on_start()
        if self.model_np is None or self.model_np.isEmpty():
            self._setup_nodes()

    def on_stop(self) -> None:
        """Called when the scene stops or the entity is deactivated; removes the model."""
        self._cleanup_nodes()
        super().on_stop()

    def on_detach(self) -> None:
        """Detach handler cleanly and remove the model instance."""
        self._cleanup_nodes()
        super().on_detach()
