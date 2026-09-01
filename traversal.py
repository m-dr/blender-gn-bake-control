import bpy


def get_reachable_nodes_in_tree(node_tree):
    """
    Find all active, unmuted nodes in a node tree that are connected
    and can reach an unmuted GROUP_OUTPUT node.
    """
    if not node_tree:
        return set()

    output_nodes = [n for n in node_tree.nodes if n.type == 'GROUP_OUTPUT' and not n.mute]
    if not output_nodes:
        # Fallback if no explicit group output node: all unmuted nodes
        return set(n for n in node_tree.nodes if not n.mute)

    # Build upstream adjacency map: to_node -> list of from_nodes
    upstream_adj = {n: [] for n in node_tree.nodes}
    for link in node_tree.links:
        if link.is_valid:
            if not link.from_node.mute and not link.to_node.mute:
                upstream_adj[link.to_node].append(link.from_node)

    # Backward BFS from unmuted outputs
    visited = set(output_nodes)
    queue = list(output_nodes)
    while queue:
        curr = queue.pop(0)
        for prev in upstream_adj.get(curr, []):
            if prev not in visited:
                visited.add(prev)
                queue.append(prev)

    return visited


def find_bake_nodes_in_tree(node_tree, prefix=""):
    """
    Recursively find all connected, unmuted bake nodes in a node tree in topological execution order.
    """
    if not node_tree:
        return []

    reachable = get_reachable_nodes_in_tree(node_tree)

    in_degree = {n: 0 for n in node_tree.nodes}
    adj = {n: [] for n in node_tree.nodes}

    for link in node_tree.links:
        if link.is_valid and link.from_node in in_degree and link.to_node in in_degree:
            # Only consider links between unmuted, reachable nodes
            if not link.from_node.mute and not link.to_node.mute:
                adj[link.from_node].append(link.to_node)
                in_degree[link.to_node] += 1

    queue = [n for n, deg in in_degree.items() if deg == 0 and n in reachable and not n.mute]
    queue.sort(key=lambda n: (n.location.x, -n.location.y))

    ordered_nodes = []
    while queue:
        curr = queue.pop(0)
        ordered_nodes.append(curr)
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0 and neighbor in reachable and not neighbor.mute:
                queue.append(neighbor)
        queue.sort(key=lambda n: (n.location.x, -n.location.y))

    # Append any reachable nodes not caught by cycle detection
    for n in node_tree.nodes:
        if n in reachable and not n.mute and n not in ordered_nodes:
            ordered_nodes.append(n)

    results = []
    for node in ordered_nodes:
        if node.mute or node not in reachable:
            continue

        name = node.label if node.label else node.name
        if node.type == 'BAKE':
            path = f"{prefix}{name}" if prefix else name
            results.append({
                "name": name,
                "path": path,
                "node": node,
                "tree": node_tree,
            })
        elif node.type == 'GROUP' and getattr(node, "node_tree", None):
            sub_prefix = f"{prefix}{name} > " if prefix else f"{name} > "
            results.extend(find_bake_nodes_in_tree(node.node_tree, prefix=sub_prefix))

    return results


def get_object_bake_list(obj, scene=None):
    """
    Return a clean list of modifiers and all their connected, active bake nodes with frame metadata.
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

        # Map nodes to modifier bakes collection
        bakes_collection = list(getattr(mod, "bakes", []))
        bake_by_node = {b.node: b for b in bakes_collection if getattr(b, "node", None)}
        unmapped_bakes = list(bakes_collection)

        tree_bakes = find_bake_nodes_in_tree(mod.node_group)
        mod_items = []

        for item in tree_bakes:
            node = item["node"]
            b_item = bake_by_node.get(node)
            if b_item:
                if b_item in unmapped_bakes:
                    unmapped_bakes.remove(b_item)

                has_cache = bool(getattr(b_item, "data_blocks", None) and len(b_item.data_blocks) > 0)
                mode = getattr(b_item, "bake_mode", "STILL")

                if mode == 'STILL':
                    frame_info = f"Still: Frame {scene_frame_current}"
                else:
                    if getattr(b_item, "use_custom_simulation_frame_range", False):
                        frame_info = f"Range: {b_item.frame_start}..{b_item.frame_end} (Custom)"
                    else:
                        frame_info = f"Range: {scene_frame_start}..{scene_frame_end} (Scene)"

                mod_items.append({
                    "name": item["name"],
                    "path": item["path"],
                    "node_name": node.name,
                    "tree_name": item["tree"].name if item["tree"] else "",
                    "bake_id": b_item.bake_id,
                    "mode": mode,
                    "frame_info": frame_info,
                    "has_cache": has_cache,
                    "bake_item": b_item,
                })

        # Include unmapped bakes (e.g. simulation zone outputs) if active
        for b_item in unmapped_bakes:
            node = getattr(b_item, "node", None)
            if node and node.mute:
                continue

            node_name = node.label if (node and node.label) else (node.name if node else f"Bake #{b_item.bake_id}")
            has_cache = bool(getattr(b_item, "data_blocks", None) and len(b_item.data_blocks) > 0)
            mode = getattr(b_item, "bake_mode", "STILL")

            if mode == 'STILL':
                frame_info = f"Still: Frame {scene_frame_current}"
            else:
                if getattr(b_item, "use_custom_simulation_frame_range", False):
                    frame_info = f"Range: {b_item.frame_start}..{b_item.frame_end} (Custom)"
                else:
                    frame_info = f"Range: {scene_frame_start}..{scene_frame_end} (Scene)"

            mod_items.append({
                "name": node_name,
                "path": node_name,
                "node_name": node.name if node else "",
                "tree_name": mod.node_group.name if mod.node_group else "",
                "bake_id": b_item.bake_id,
                "mode": mode,
                "frame_info": frame_info,
                "has_cache": has_cache,
                "bake_item": b_item,
            })

        if mod_items:
            modifiers_data.append({
                "modifier_name": mod.name,
                "bakes": mod_items,
            })

    return modifiers_data


get_object_bake_items = get_object_bake_list
