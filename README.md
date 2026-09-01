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

## Roadmap

### 1. Granular Frame & Range Controls
- **Custom Range Popover**: Configure custom animation/simulation start and end frame ranges per bake node using a compact popup dialog.
- **Per-Node Custom Range Toggles**: Toggle custom frame range on/off directly from each row in the UI.
- **Batch Range Management**:
  - Batch apply/offset custom start and end frame ranges across selected or all nodes.
  - Batch toggle custom frame range modes on or off.
- **Per-Node Static Frame Overrides**: Adjust custom static target frames per individual static bake item directly from the list.

### 2. Cache Storage, Packing & Node Settings Parity
- **Full Node Settings Parity**: Expose all native bake node settings (generation settings, attributes, custom paths) in the add-on UI.
- **Pack & Unpack Controls**: Inspect, pack, and unpack bake caches directly from the list.
- **Batch Storage Mode Switching**: Batch toggle between `Disk` and `Packed` (internal) cache storage across modifiers and nodes.
- **Default Storage Policy**: Option to automatically force modifiers to use the `Disk` caching method by default.

### 3. Path Management & Smart Cache Lifecycle
- **Path Conflict Resolution**: Automatically discover and resolve conflicting cache paths between modifiers and bake nodes.
- **Batch Path Regeneration**: Batch clear/reset custom bake paths so new unique directories are generated, preventing accidental overwriting of caches from previous `.blend` file versions.
- **Smart Obsolete Cache Cleanup**:
  - Detect and safely clean up orphaned/obsolete cache files from older `.blend` file version increments.
  - Object-specific matching to strictly guarantee cache files belonging to other objects in the same project are never touched.

### 4. Navigation & Graph Overview
- **Nested Node Editor Navigation**: Robust cross-hierarchy jumping and framing into deeply nested node groups and modifier spaces.
- **Scene-Wide Dependency Overview**: Scene-level overview across all objects and modifiers in the scene.

---

## License

GPL-3.0-or-later
