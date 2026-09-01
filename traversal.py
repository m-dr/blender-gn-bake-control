import os
import bpy


def get_reachable_nodes_in_tree(node_tree):
    """
    Find all nodes in a node tree that have a valid link path leading to a GROUP_OUTPUT node.
    """
    if not node_tree:
        return set()

    output_nodes = [n for n in node_tree.nodes if n.type == 'GROUP_OUTPUT']
    if not output_nodes:
        # If no explicit group output, consider nodes with linked outputs as connected
        return set(n for n in node_tree.nodes if len(n.outputs) > 0 and any(s.is_linked for s in n.outputs))

    upstream_adj = {n: [] for n in node_tree.nodes}
    for link in node_tree.links:
        if link.is_valid:
            upstream_adj[link.to_node].append(link.from_node)

    visited = set(output_nodes)
    queue = list(output_nodes)
    while queue:
        curr = queue.pop(0)
        for prev in upstream_adj.get(curr, []):
            if prev not in visited:
                visited.add(prev)
                queue.append(prev)

    return visited


def traverse_tree_bakes(node_tree, prefix="", depth=0, is_parent_connected=True, is_parent_muted=False):
    """
    Recursively find all bake nodes and simulation outputs in a node tree in topological execution order.
    Returns (connected_bakes, disconnected_bakes).
    """
    if not node_tree:
        return [], []

    reachable = get_reachable_nodes_in_tree(node_tree)

    in_degree = {n: 0 for n in node_tree.nodes}
    adj = {n: [] for n in node_tree.nodes}

    for link in node_tree.links:
        if link.is_valid and link.from_node in in_degree and link.to_node in in_degree:
            adj[link.from_node].append(link.to_node)
            in_degree[link.to_node] += 1

    queue = [n for n, deg in in_degree.items() if deg == 0]
    queue.sort(key=lambda n: (n.location.x, -n.location.y))

    ordered_nodes = []
    while queue:
        curr = queue.pop(0)
        ordered_nodes.append(curr)
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)
        queue.sort(key=lambda n: (n.location.x, -n.location.y))

    for n in node_tree.nodes:
        if n not in ordered_nodes:
            ordered_nodes.append(n)

    connected_bakes = []
    disconnected_bakes = []

    for node in ordered_nodes:
        name = node.label if node.label else node.name
        path = f"{prefix}{name}" if prefix else name
        node_conn = is_parent_connected and (node in reachable)
        node_muted = is_parent_muted or bool(getattr(node, "mute", False))

        if node.type in ('BAKE', 'SIMULATION_OUTPUT'):
            item = {
                "name": name,
                "path": path,
                "node": node,
                "tree": node_tree,
                "depth": depth,
                "is_connected": node_conn,
                "is_muted": node_muted,
                "is_simulation": node.type == 'SIMULATION_OUTPUT',
            }
            if node_conn:
                connected_bakes.append(item)
            else:
                disconnected_bakes.append(item)

        elif node.type == 'GROUP' and getattr(node, "node_tree", None):
            group_name = node.label if node.label else node.node_tree.name
            sub_prefix = f"{prefix}{group_name} > " if prefix else f"{group_name} > "
            sub_conn, sub_dis = traverse_tree_bakes(
                node.node_tree,
                prefix=sub_prefix,
                depth=depth + 1,
                is_parent_connected=node_conn,
                is_parent_muted=node_muted,
            )
            connected_bakes.extend(sub_conn)
            disconnected_bakes.extend(sub_dis)

    return connected_bakes, disconnected_bakes


def check_bake_has_cache(bake_item):
    """Accurately check if a bake item has cached simulation or geometry data."""
    if not bake_item:
        return False
    try:
        # Check internal collection
        if getattr(bake_item, "data_blocks", None) and len(bake_item.data_blocks) > 0:
            return True
        # Check disk directory
        if getattr(bake_item, "bake_target", "") == 'DISK' and getattr(bake_item, "directory", ""):
            cache_dir = bpy.path.abspath(bake_item.directory)
            if os.path.exists(cache_dir) and len(os.listdir(cache_dir)) > 0:
                return True
    except Exception:
        pass
    return False


def get_object_bake_list(obj, scene=None, show_disconnected=True):
    """
    Return all modifiers and their bake nodes (connected in wiring order, disconnected at bottom)
    with tree connectors and single action execution metadata.
    """
    if not obj or not hasattr(obj, "modifiers"):
        return []

    if scene is None:
        scene = bpy.context.scene if hasattr(bpy, "context") and bpy.context else None

    scene_frame_current = scene.frame_current if scene else 1
    scene_frame_start = scene.frame_start if scene else 1
    scene_frame_end = scene.frame_end if scene else 250

    modifiers_data = []
    for mod in obj.modifiers:
        if mod.type != 'NODES' or not mod.node_group:
            continue

        bakes_collection = list(getattr(mod, "bakes", []))
        bake_by_node = {b.node: b for b in bakes_collection if getattr(b, "node", None)}
        unmapped_bakes = list(bakes_collection)

        conn_tree_bakes, dis_tree_bakes = traverse_tree_bakes(mod.node_group)

        def build_bake_info(item):
            node = item.get("node")
            b_item = bake_by_node.get(node)
            if b_item and b_item in unmapped_bakes:
                unmapped_bakes.remove(b_item)

            has_cache = check_bake_has_cache(b_item)
            mode = getattr(b_item, "bake_mode", "ANIMATION" if item.get("is_simulation") else "STILL")

            if mode == 'STILL':
                frame_info = f"Frame {scene_frame_current}"
            else:
                if b_item and getattr(b_item, "use_custom_simulation_frame_range", False):
                    frame_info = f"{b_item.frame_start} – {b_item.frame_end} (Cust)"
                else:
                    frame_info = f"{scene_frame_start} – {scene_frame_end}"

            return {
                "name": item["name"],
                "path": item["path"],
                "node_name": node.name if node else "",
                "tree_name": item["tree"].name if item.get("tree") else "",
                "bake_id": b_item.bake_id if b_item else 0,
                "mode": mode,
                "frame_info": frame_info,
                "has_cache": has_cache,
                "depth": item.get("depth", 0),
                "is_connected": item.get("is_connected", True),
                "is_muted": item.get("is_muted", False),
                "is_simulation": item.get("is_simulation", False),
                "bake_item": b_item,
            }

        connected_items = [build_bake_info(it) for it in conn_tree_bakes]
        disconnected_items = [build_bake_info(it) for it in dis_tree_bakes]

        # Remaining unmapped bakes in mod.bakes (e.g. deleted or unlinked nodes)
        for b_item in unmapped_bakes:
            node = getattr(b_item, "node", None)
            node_name = node.label if (node and node.label) else (node.name if node else f"Bake #{b_item.bake_id}")
            has_cache = check_bake_has_cache(b_item)
            mode = getattr(b_item, "bake_mode", "STILL")

            if mode == 'STILL':
                frame_info = f"Frame {scene_frame_current}"
            else:
                if getattr(b_item, "use_custom_simulation_frame_range", False):
                    frame_info = f"{b_item.frame_start} – {b_item.frame_end} (Cust)"
                else:
                    frame_info = f"{scene_frame_start} – {scene_frame_end}"

            disconnected_items.append({
                "name": node_name,
                "path": f"{node_name} (Unlinked)",
                "node_name": node.name if node else "",
                "tree_name": mod.node_group.name if mod.node_group else "",
                "bake_id": b_item.bake_id,
                "mode": mode,
                "frame_info": frame_info,
                "has_cache": has_cache,
                "depth": 0,
                "is_connected": False,
                "is_muted": node.mute if node else False,
                "is_simulation": getattr(node, "type", "") == 'SIMULATION_OUTPUT',
                "bake_item": b_item,
            })

        all_mod_bakes = connected_items + (disconnected_items if show_disconnected else [])

        # Assign tree branch connector strings
        for i, b in enumerate(all_mod_bakes):
            is_last = (i == len(all_mod_bakes) - 1)
            depth = b.get("depth", 0)
            if depth == 0:
                b["tree_connector"] = "└── " if is_last else "├── "
            else:
                b["tree_connector"] = ("│   " * (depth - 1)) + ("└── " if is_last else "├── ")

        if all_mod_bakes:
            modifiers_data.append({
                "modifier_name": mod.name,
                "is_enabled": mod.show_viewport,
                "connected_count": len(connected_items),
                "disconnected_count": len(disconnected_items),
                "bakes": all_mod_bakes,
            })

    return modifiers_data


get_object_bake_items = get_object_bake_list
