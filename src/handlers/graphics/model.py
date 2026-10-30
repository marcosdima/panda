from __future__ import annotations
from src.utils.handler_phase import HandlerPhase

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
    phase = HandlerPhase.POST
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
        except Exception:
            logger.warning("Failed to load model '%s'.", full_path, exc_info=True)
            return None
        if template is None or template.isEmpty():
            logger.warning("Model '%s' resolved to an empty NodePath.", full_path)
            return None
        return template

    def _target_parent(self) -> NodePath | None:
        """Return the authoritative parent NodePath (dynamic body_np if present, else entity.node)."""
        if self.entity is None:
            return None
        from src.handlers.physics.rigid_body import RigidBodyHandler

        rigid = self.entity.get_handler(RigidBodyHandler)
        if (
            rigid is not None
            and rigid.is_dynamic
            and rigid.body_np is not None
            and not rigid.body_np.isEmpty()
        ):
            return rigid.body_np
        return self.entity.node

    def _setup_nodes(self) -> None:
        """Create the model instance under the authoritative parent and apply configured transforms."""
        if self.entity is None:
            return

        target_parent = self._target_parent()
        if target_parent is None or target_parent.isEmpty():
            return

        if self.model_np is not None and not self.model_np.isEmpty():
            if self.model_np.getParent() != target_parent:
                self.model_np.reparentTo(target_parent)
            return

        template = self._load_template()
        if template is None:
            self.model_np = NodePath("ModelFallback")
            self.model_np.reparentTo(target_parent)
            return

        self.model_np = template.copyTo(target_parent)
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
        """Called when the active scene or entity starts; rebuilds or reparents the model if needed."""
        super().on_start()
        self._setup_nodes()

    def on_stop(self) -> None:
        """Called when the scene stops or the entity is deactivated; removes the model."""
        super().on_stop()
        self._cleanup_nodes()

    def on_detach(self) -> None:
        """Detach handler cleanly and remove the model instance."""
        super().on_detach()
        self._cleanup_nodes()
