from typing import ClassVar, Literal

from direct.showbase.Loader import Loader
from panda3d.core import NodePath

from config import ASSETS_PATH

from .__global import Global

ModelKey = Literal["box", "panda", "environment", "teapot"]


class GlobalLoader(Global):
    """A singleton class to manage the global loader object."""

    __models: ClassVar[dict[str, NodePath]] = {}  # Cache for loaded models.

    @classmethod
    def get_global_loader(cls) -> Loader:
        """Get the global loader object."""
        if not hasattr(cls, "_instance"):
            cls()
        base = cls._instance.base
        loader = getattr(base, "loader", None) if base is not None else None
        if loader is None:
            raise Exception("Loader is not initialized.")
        return loader

    @classmethod
    def load(cls, asset_path: str) -> NodePath:
        """Internal loader with caching."""
        if asset_path in cls.__models:
            cached = cls.__models[asset_path]
            if cached is not None and not cached.isEmpty():
                return cached

        model = cls.get_global_loader().loadModel(asset_path)
        cls.__models[asset_path] = model
        return model

    @classmethod
    def load_copy(cls, asset_path: str, parent: NodePath | None = None) -> NodePath:
        """Load a cached model template and return a fresh deep-copied NodePath instance."""
        template = cls.load(asset_path)
        if parent is not None and not parent.isEmpty():
            return template.copyTo(parent)
        temp_parent = NodePath("loader_copy_root")
        instance = template.copyTo(temp_parent)
        instance.detachNode()
        return instance

    @classmethod
    def load_from_assets(cls, relative_path: str) -> NodePath:
        """Load a model from the assets folder using caching."""
        full_path = ASSETS_PATH + relative_path
        return cls.load(full_path)

    @classmethod
    def load_panda_asset(cls, model: ModelKey) -> NodePath:
        """Load a default Panda3D model by key using caching."""
        default_models = {
            "box": "models/box",
            "panda": "models/panda",
            "environment": "models/environment",
            "teapot": "models/teapot",
        }

        asset_path = default_models[model]
        return cls.load(asset_path)

    @classmethod
    def load_actor(
        cls, asset_path: str, animations: dict[str, str] | None = None
    ) -> NodePath:
        """Load an Actor model from the given asset path using caching."""
        import gltf  # noqa: F401
        from direct.actor.Actor import Actor

        cache_key = f"{asset_path}:{sorted(animations.items()) if animations else None}"
        template = cls.__models.get(cache_key)
        if template is None or (hasattr(template, "isEmpty") and template.isEmpty()):
            full_path = ASSETS_PATH + asset_path

            # If animations are provided, prepend ASSETS_PATH to each one
            if animations:
                full_animations = {
                    name: ASSETS_PATH + path for name, path in animations.items()
                }
                template = Actor(full_path, anims=full_animations)
            else:
                # Load without animations - will use embedded animations if present
                template = Actor(full_path)

            cls.__models[cache_key] = template
            cls.__models[asset_path] = template

        return Actor(other=template)
