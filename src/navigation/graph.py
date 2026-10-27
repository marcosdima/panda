from __future__ import annotations

import heapq
from collections.abc import Sequence

from panda3d.core import Vec3


class NavGraph:
    """A weighted graph used for pathfinding between named nodes."""

    def __init__(self) -> None:
        self.nodes: dict[object, Vec3] = {}
        self._edges: dict[object, list[tuple[object, float]]] = {}

    def add_node(self, node_id: object, position: Vec3 | Sequence[float]) -> None:
        self.nodes[node_id] = Vec3(position)
        self._edges.setdefault(node_id, [])

    def remove_node(self, node_id: object) -> None:
        self.nodes.pop(node_id, None)
        self._edges.pop(node_id, None)
        for edges in self._edges.values():
            edges[:] = [e for e in edges if e[0] != node_id]

    def add_edge(
        self,
        a: object,
        b: object,
        cost: float | None = None,
        bidirectional: bool = True,
    ) -> None:
        if a not in self.nodes or b not in self.nodes:
            raise KeyError("both nodes must exist before adding an edge")
        if cost is None:
            cost = (self.nodes[a] - self.nodes[b]).length()
        self._edges.setdefault(a, []).append((b, float(cost)))
        if bidirectional:
            self._edges.setdefault(b, []).append((a, float(cost)))

    def neighbors(self, node_id: object) -> list[tuple[object, float]]:
        return list(self._edges.get(node_id, ()))

    def node_position(self, node_id: object) -> Vec3:
        return Vec3(self.nodes[node_id])

    def nearest_node(self, position: Vec3 | Sequence[float]) -> object | None:
        if not self.nodes:
            return None
        best = None
        best_dist = float("inf")
        for node_id, node_pos in self.nodes.items():
            dist = (Vec3(node_pos) - Vec3(position)).length()
            if dist < best_dist:
                best_dist = dist
                best = node_id
        return best

    def find_path(self, start: object, goal: object) -> list[Vec3] | None:
        return GraphPathfinder(self).find_path(start, goal)


class GraphPathfinder:
    def __init__(self, graph: NavGraph) -> None:
        self.graph = graph

    def find_path(self, start: object, goal: object) -> list[Vec3] | None:
        graph = self.graph
        # Resolve positions to node ids when needed.
        start_id = start if start in graph.nodes else graph.nearest_node(start)
        goal_id = goal if goal in graph.nodes else graph.nearest_node(goal)
        if start_id is None or goal_id is None:
            return None
        if start_id == goal_id:
            return [graph.node_position(start_id)]

        open_heap: list[tuple[float, int, object]] = []
        counter = 0
        heapq.heappush(open_heap, (0.0, counter, start_id))
        came_from: dict[object, object | None] = {start_id: None}
        g_score: dict[object, float] = {start_id: 0.0}

        while open_heap:
            _, _, current = heapq.heappop(open_heap)
            if current == goal_id:
                break
            for neighbour, cost in graph.neighbors(current):
                tentative = g_score[current] + cost
                if neighbour not in g_score or tentative < g_score[neighbour]:
                    g_score[neighbour] = tentative
                    came_from[neighbour] = current
                    priority = tentative + self._heuristic(current, neighbour, goal_id)
                    counter += 1
                    heapq.heappush(open_heap, (priority, counter, neighbour))

        if goal_id not in came_from:
            return None

        node_ids: list[object] = []
        cur: object | None = goal_id
        while cur is not None:
            node_ids.append(cur)
            cur = came_from[cur]
        node_ids.reverse()
        return [graph.node_position(nid) for nid in node_ids]

    def _heuristic(self, _current: object, neighbour: object, goal_id: object) -> float:
        graph = self.graph
        return (graph.node_position(neighbour) - graph.node_position(goal_id)).length()
