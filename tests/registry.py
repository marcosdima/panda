"""Central registry of test scenes.

Maps a short scene key to a ``(title, category, scene_class)`` tuple. The
playground uses this registry to discover and launch scenes; ``category`` is
either ``"visual"`` (Panda3D sandbox under ``tests.panda``) or
``"integration"`` (in-engine suite under ``tests.terminal``).

Importing this module imports every registered scene class, so it is the single
source of truth for the available scenes.
"""

from __future__ import annotations

from .panda.ai_sandbox import TestAISandbox
from .panda.animation_blend_sandbox import TestAnimationBlendSandbox
from .panda.animation_sandbox import TestAnimationSandbox
from .panda.camera_sandbox import TestFirstPersonCameraSandbox
from .panda.character_sandbox import TestCharacterSandbox
from .panda.follow_sandbox import TestFollowSandbox
from .panda.mini_game_sandbox import TestMiniGameSandbox
from .panda.models import TestModels
from .panda.physics import TestPhysics
from .panda.proximity_sandbox import TestProximitySandbox
from .panda.triggers_sandbox import TestTriggersSandbox
from .terminal.actor_animation import TestActorAnimation
from .terminal.camera_handler import TestCameraHandler
from .terminal.character_controller import TestCharacterController
from .terminal.entities import TestEntities
from .terminal.events import TestEvents
from .terminal.model_handler import TestModelHandler
from .terminal.physics_handlers import TestPhysicsHandlers
from .terminal.prefab_smoke_test import TestPrefabSmoke
from .terminal.scene_tasks_test import TestSceneTasks

SCENE_REGISTRY: dict[str, tuple[str, str, type]] = {
    # Visual sandboxes (launched in an isolated subprocess by the playground).
    "ai": ("AI Sandbox", "visual", TestAISandbox),
    "animation_blend": ("Animation Blend Sandbox", "visual", TestAnimationBlendSandbox),
    "animation_state": ("Animation State Sandbox", "visual", TestAnimationSandbox),
    "camera_fp": (
        "First-Person Camera Sandbox",
        "visual",
        TestFirstPersonCameraSandbox,
    ),
    "character": ("Character Sandbox", "visual", TestCharacterSandbox),
    "follow": ("Follow Sandbox", "visual", TestFollowSandbox),
    "mini_game": ("Mini Game Sandbox", "visual", TestMiniGameSandbox),
    "models": ("Models Sandbox", "visual", TestModels),
    "physics": ("Physics Sandbox", "visual", TestPhysics),
    "proximity": ("Proximity Sandbox", "visual", TestProximitySandbox),
    "triggers": ("Triggers Sandbox", "visual", TestTriggersSandbox),
    # In-engine integration suites (executed via tests.terminal.run_all).
    "actor_animation": (
        "Actor Animation (terminal)",
        "integration",
        TestActorAnimation,
    ),
    "camera_handler": ("Camera Handler (terminal)", "integration", TestCameraHandler),
    "character_controller": (
        "Character Controller (terminal)",
        "integration",
        TestCharacterController,
    ),
    "entities": ("Entities (terminal)", "integration", TestEntities),
    "events": ("Events (terminal)", "integration", TestEvents),
    "model_handler": ("Model Handler (terminal)", "integration", TestModelHandler),
    "physics_handlers": (
        "Physics Handlers (terminal)",
        "integration",
        TestPhysicsHandlers,
    ),
    "prefab_smoke": ("Prefab Smoke (terminal)", "integration", TestPrefabSmoke),
    "scene_tasks": ("Scene Tasks (terminal)", "integration", TestSceneTasks),
}


__all__ = ["SCENE_REGISTRY"]
