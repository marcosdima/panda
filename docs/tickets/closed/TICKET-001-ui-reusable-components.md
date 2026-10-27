# UI-001 — Reusable UI components (buttons, lists, scroll) for playground and sandboxes

- **Estado:** Open
- **Área:** ui
- **Motivación:** The playground and sandboxes currently build their overlays with
  `OnscreenText` and raw key bindings because `DirectGui` is underdeveloped in
  this codebase. There is no reusable button, list or scroll component, so every
  scene reimplements the same boilerplate and the playground cannot offer real
  clickable controls.
- **Propuesta:** Introduce a small set of reusable UI primitives (button, vertical
  list, scroll container) built on top of the existing Panda3D tooling, with a
  consistent styling API, and migrate the playground menu to use them.
- **Criterio de cierre:** Playground menu and at least one sandbox use the new
  components; components have a documented public API and a smoke test.
