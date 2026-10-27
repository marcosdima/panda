from .follow import FollowHandler, FollowState
from .navigation import AINavigationHandler, NavigationState
from .patrol import AIPatrolHandler, PatrolState

# Compatibility aliases for alternative naming.
AIPathPatrolHandler = AINavigationHandler
PathfindingHandler = AINavigationHandler
PathPatrolHandler = AINavigationHandler
NavigationHandler = AINavigationHandler

AIState = NavigationState
PathPatrolState = NavigationState
PathState = NavigationState

__all__ = [
    "AIPatrolHandler",
    "PatrolState",
    "AINavigationHandler",
    "NavigationState",
    "AIPathPatrolHandler",
    "PathfindingHandler",
    "PathPatrolHandler",
    "NavigationHandler",
    "AIState",
    "PathPatrolState",
    "PathState",
    "FollowHandler",
    "FollowState",
]
