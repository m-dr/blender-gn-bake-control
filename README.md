# GN Bake Control

**GN Bake Control** is a Blender 5.2+ extension designed to streamline baking workflows for Geometry Nodes. It automatically discovers and organizes bake nodes across all Geometry Nodes modifiers on an object in their **topological execution order**, providing a compact, high-performance interface for batch baking, rebaking, cleaning, and fine-tuning individual bake parameters.

---

## Features

- **Topological Execution Traversal**:
  - Traverses modifiers from top-to-bottom and inspects node graphs (including nested node groups) from group inputs to outputs.
  - Lists bake nodes in the exact order they execute along the node graph flow.

- **Batch Operations**:
  - **Bake Selected**: Sequentially executes bakes for all selected bake nodes.
  - **Rebake**: Cleans existing cache and immediately bakes fresh.
  - **Clean / Clear**: Cleans cache data across selected bake nodes.
  - **Modal Timer Engine**: Keeps Blender responsive with real-time status bar progress and `ESC` cancellation support.

- **Per-Node Controls**:
  - **Bake Mode**: Toggle between `Still` and `Animation` directly from the list.
  - **Custom Still Target Frame**: Set a specific target frame to evaluate and bake on for still bakes without having to permanently change your scene frame.
  - **Custom Animation Range**: Configure custom start and end simulation/animation frame ranges per bake node.
  - **Jump to Node**: Quickly open and center on the corresponding node inside the Geometry Node Editor.
  - **One-Click Actions**: Individual bake and clean buttons on every row.

- **Compact & Clean UI**:
  - Dense row layout prevents modifier panels from becoming excessively tall when working with many bake nodes.
  - Filter search bar and "Missing Only" toggle to quickly locate specific nodes.
  - Bulk selection helpers (`All`, `None`, `Invert`).

- **Flexible Panel Placement**:
  - Located on top of the Modifier Stack in `Properties > Modifiers`.
  - Located in the 3D Viewport Sidebar (`N-Panel > GN Bake`).
  - Both panel locations are customizable and toggleable in Add-on Preferences.

---

## Installation

### As an Extension (Blender 4.2 / 5.2+)
1. Download `gn_bake_control-<version>.zip` from the releases or build it using `python scripts/build_extension.py`.
2. In Blender, go to **Edit > Preferences > Get Extensions**.
3. Click the dropdown menu in the top right and choose **Install from Disk...**.
4. Select the `.zip` package.

## Roadmap (Prioritized)

> **Design Principle**: All UI draw routines and data lookups must remain strictly **lazy and lightweight**, ensuring zero viewport lag, minimal Python overhead, and high responsiveness even on massive node trees.

### Phase 1: Core Node Parameter Controls & UI Parity *(Top Priority)*
Expose full control for all native Geometry Nodes bake parameters directly in the add-on interface (via popovers and inline controls):
- **Custom Time Range Popover**: Configure animation/simulation start & end frame ranges per bake node directly via a compact popup dialog.
- **Per-Node & Batch Custom Range Toggles**: Toggle custom frame range on/off per individual node or in bulk across all nodes.
- **Batch Time Range Management**: Batch set or offset custom frame ranges across multiple bake nodes simultaneously.
- **Per-Node Static Frame Overrides**: Set custom target frames per static bake item directly from the list.
- **Pack & Unpack Controls**: Direct UI controls for inspecting, packing, and unpacking individual bake caches.
- **Storage Target Switching**: Batch switch between `Disk` and `Packed` (internal) cache storage across modifiers and nodes.
- **Default Storage Policy**: Global preference to automatically enforce the `Disk` caching method on newly created or traversed modifiers.
- **Full Settings Parity**: Expose generation settings, sub-frame step sampling, and attribute bake filters.

### Phase 2: Cache Lifecycle, Path Conflicts & Navigation *(High Priority)*
- **Path Conflict Detection & Resolution**: Identify and resolve overlapping or conflicting cache directories between different modifiers or nodes.
- **Batch Path Regeneration**: Batch clear and regenerate custom bake paths to prevent accidental cache overwriting across `.blend` version increments.
- **Smart Obsolete Cache Cleanup**: Scan disk folders to clean up orphaned cache files from older `.blend` version increments, with strict object-matching to safeguard other objects' caches.
- **Nested Node Editor Navigation**: Robust cross-hierarchy jumping and framing across deeply nested node groups and modifier spaces.

### Phase 3: Production Diagnostics & Safety *(Medium Priority)*
- **Pre-Render Safety Hook (`render_pre`)**: Automated pre-flight check when triggering `F12` / `Ctrl+F12` to warn against unbaked or stale simulation nodes, with an optional auto-rebake option.
- **Disk Storage Footprint Monitoring**: Display disk cache sizes per node (e.g. `120 MB`, `3.2 GB`) and a total cache size summary for the active object.
- **"Open Folder in Explorer"**: 1-click button to jump directly into the node's disk cache folder.
- **Cache Health & Integrity Check**: Quick verification to detect missing or corrupt `.blob` sequence files.

### Phase 4: Advanced Studio Workflows & Background Baking *(Future Polish)*
- **Background / Headless Process Baking**: Spawn detached background Blender CLI worker processes (`blender -b`) for massive simulations without locking the interactive session.
- **Cache Iterations & Snapshots**: Save, name, and switch between multiple bake snapshots (`v1`, `v2`, `v3`) for parameter comparison without destroying previous runs.
- **Smart Node Auto-Naming**: Auto-label generic bake nodes based on upstream connected groups (e.g. `Bake [Point Repulsion]`).
- **Batch Finish Notifications**: OS desktop notifications or audio chimes on long batch bake completion.
- **Scene-Wide Master Overview**: Centralized multi-object overview displaying all Geometry Nodes bakes across the entire scene.

---

## License

GPL-3.0-or-later
