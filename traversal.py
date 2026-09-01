import os
from collections import defaultdict
import bpy


def get_reachable_nodes_in_tree(node_tree):
    """
    Find all nodes in a node tree that have a valid link path leading to a GROUP_OUTPUT node.
    """
    if not node_tree:
        return set()

    output_nodes = [n for n in node_tree.nodes if n.type == 'GROUP_OUTPUT']
    if not output_nodes:
        return set(n for n in node_tree.nodes if len(n.outputs) > 0 and any(s.is_linked for s in n.outputs))

    upstream_adj = defaultdict(list)
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


def node_tree_has_bakes(node_tree, visited=None):
    """Check recursively if a node tree contains any BAKE or SIMULATION_OUTPUT nodes."""
    if not node_tree:
        return False
    if visited is None:
        visited = set()
    if node_tree in visited:
        return False
    visited.add(node_tree)

    for n in node_tree.nodes:
        if n.type in ('BAKE', 'SIMULATION_OUTPUT'):
            return True
        if n.type == 'GROUP' and getattr(n, "node_tree", None):
            if node_tree_has_bakes(n.node_tree, visited):
                return True
    return False


def compute_tree_bake_stages(node_tree, prefix_stage="", depth=0, group_hierarchy=None, is_parent_connected=True, is_parent_muted=False):
    """
    Compute DAG longest-path topological execution stages and hierarchical number tags (e.g. 1.1, 1.2, 2, 2.1, 3).
    Returns (connected_items, disconnected_items).
    """
    if not node_tree:
        return [], []

    if group_hierarchy is None:
        group_hierarchy = []

    reachable = get_reachable_nodes_in_tree(node_tree)

    upstream_adj = defaultdict(list)
    downstream_adj = defaultdict(list)
    for link in node_tree.links:
        if link.is_valid:
            upstream_adj[link.to_node].append(link.from_node)
            downstream_adj[link.from_node].append(link.to_node)

    # In-degree of reachable nodes for topological ordering
    in_degree = {n: 0 for n in reachable}
    for n in reachable:
        for prev in upstream_adj[n]:
            if prev in reachable:
                in_degree[n] += 1

    topo_order = []
    zero_q = [n for n, d in in_degree.items() if d == 0]
    zero_q.sort(key=lambda n: (n.location.x, -n.location.y))
    while zero_q:
        curr = zero_q.pop(0)
        topo_order.append(curr)
        for nxt in downstream_adj[curr]:
            if nxt in in_degree:
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    zero_q.append(nxt)
        zero_q.sort(key=lambda n: (n.location.x, -n.location.y))

    # Identify interesting nodes in active data-flow (Bakes, Sim zones, or Groups with bakes)
    interesting_nodes = []
    for n in topo_order:
        if n.type in ('BAKE', 'SIMULATION_OUTPUT'):
            interesting_nodes.append(n)
        elif n.type == 'GROUP' and getattr(n, "node_tree", None) and node_tree_has_bakes(n.node_tree):
            interesting_nodes.append(n)

    # Compute longest path stage from preceding interesting nodes
    stages = {}
    for n in interesting_nodes:
        max_prev_stage = 0
        visited_up = set()
        up_q = list(upstream_adj[n])
        while up_q:
            u = up_q.pop(0)
            if u in visited_up:
                continue
            visited_up.add(u)
            if u in stages and stages[u] > max_prev_stage:
                max_prev_stage = stages[u]
            for prev_u in upstream_adj[u]:
                if prev_u in reachable and prev_u not in visited_up:
                    up_q.append(prev_u)
        stages[n] = max_prev_stage + 1

    by_stage = defaultdict(list)
    for n in interesting_nodes:
        by_stage[stages[n]].append(n)

    connected_items = []
    max_stage = max(by_stage.keys()) if by_stage else 0
    total_stages = len(by_stage)

    for stage_num in sorted(by_stage.keys()):
        stage_nodes = by_stage[stage_num]
        stage_nodes.sort(key=lambda n: (n.location.x, -n.location.y))
        has_siblings = len(stage_nodes) > 1

        for idx, node in enumerate(stage_nodes, 1):
            if prefix_stage:
                if total_stages == 1:
                    # Single internal stage in sub-group: append sibling index directly
                    num_tag = f"{prefix_stage}.{idx}" if has_siblings else f"{prefix_stage}.1"
                else:
                    # Multiple internal stages in sub-group
                    num_tag = f"{prefix_stage}.{stage_num}.{idx}" if has_siblings else f"{prefix_stage}.{stage_num}"
            else:
                num_tag = f"{stage_num}.{idx}" if has_siblings else f"{stage_num}"

            name = node.label if node.label else node.name
            node_muted = is_parent_muted or bool(getattr(node, "mute", False))

            if node.type in ('BAKE', 'SIMULATION_OUTPUT'):
                connected_items.append({
                    "name": name,
                    "num_tag": num_tag,
                    "group_name": " > ".join(group_hierarchy) if group_hierarchy else "",
                    "depth": depth,
                    "node": node,
                    "tree": node_tree,
                    "is_group": False,
                    "is_connected": is_parent_connected,
                    "is_muted": node_muted,
                    "is_simulation": node.type == 'SIMULATION_OUTPUT',
                })
            elif node.type == 'GROUP' and getattr(node, "node_tree", None):
                group_name = node.label if node.label else node.node_tree.name
                sub_conn, sub_dis = compute_tree_bake_stages(
                    node.node_tree,
                    prefix_stage=num_tag,
                    depth=depth + 1,
                    group_hierarchy=group_hierarchy + [group_name],
                    is_parent_connected=is_parent_connected,
                    is_parent_muted=node_muted,
                )
                connected_items.append({
                    "name": group_name,
                    "num_tag": num_tag,
                    "group_name": " > ".join(group_hierarchy) if group_hierarchy else "",
                    "depth": depth,
                    "node": node,
                    "tree": node_tree,
                    "is_group": True,
                    "group_tree": node.node_tree,
                    "is_connected": is_parent_connected,
                    "is_muted": node_muted,
                    "is_simulation": False,
                    "children": sub_conn,
                })

    # Disconnected nodes (not reachable from GROUP_OUTPUT)
    disconnected_items = []
    disc_nodes = [
        n for n in node_tree.nodes
        if n not in reachable and n.type in ('BAKE', 'SIMULATION_OUTPUT')
    ]
    disc_nodes.sort(key=lambda n: (n.location.x, -n.location.y))

    for i, dn in enumerate(disc_nodes, 1):
        num_tag = f"{max_stage + i}" if not prefix_stage else f"{prefix_stage}.{max_stage + i}"
        name = dn.label if dn.label else dn.name
        disconnected_items.append({
            "name": name,
            "num_tag": num_tag,
            "group_name": " > ".join(group_hierarchy) if group_hierarchy else "",
            "depth": depth,
            "node": dn,
            "tree": node_tree,
            "is_group": False,
            "is_connected": False,
            "is_muted": dn.mute if hasattr(dn, "mute") else False,
            "is_simulation": dn.type == 'SIMULATION_OUTPUT',
        })

    return connected_items, disconnected_items


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
    Return all modifiers and their bake nodes in hierarchical DAG execution sequence
    with number badges ([1.1], [1.2], [2], [2.1], [3]), group encapsulation, depth, and metadata.
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

        conn_tree, dis_tree = compute_tree_bake_stages(mod.node_group)

        def flatten_items(item_list):
            flat = []
            for item in item_list:
                if item.get("is_group"):
                    flat.append(item)
                    flat.extend(flatten_items(item.get("children", [])))
                else:
                    flat.append(item)
            return flat

        all_conn_items = flatten_items(conn_tree)
        all_dis_items = flatten_items(dis_tree)

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
                "num_tag": item.get("num_tag", ""),
                "group_name": item.get("group_name", ""),
                "depth": item.get("depth", 0),
                "node_name": node.name if node else "",
                "tree_name": item["tree"].name if item.get("tree") else "",
                "bake_id": b_item.bake_id if b_item else 0,
                "mode": mode,
                "frame_info": frame_info,
                "has_cache": has_cache,
                "is_group": item.get("is_group", False),
                "is_connected": item.get("is_connected", True),
                "is_muted": item.get("is_muted", False),
                "is_simulation": item.get("is_simulation", False),
                "bake_item": b_item,
            }

        connected_bakes = [build_bake_info(it) for it in all_conn_items]
        disconnected_bakes = [build_bake_info(it) for it in all_dis_items]

        # Remaining unmapped bakes in mod.bakes
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

            next_idx = len(connected_bakes) + len(disconnected_bakes) + 1
            disconnected_bakes.append({
                "name": node_name,
                "num_tag": f"{next_idx}",
                "group_name": "",
                "depth": 0,
                "node_name": node.name if node else "",
                "tree_name": mod.node_group.name if mod.node_group else "",
                "bake_id": b_item.bake_id,
                "mode": mode,
                "frame_info": frame_info,
                "has_cache": has_cache,
                "is_group": False,
                "is_connected": False,
                "is_muted": node.mute if node else False,
                "is_simulation": getattr(node, "type", "") == 'SIMULATION_OUTPUT',
                "bake_item": b_item,
            })

        all_mod_bakes = connected_bakes + (disconnected_bakes if show_disconnected else [])

        if all_mod_bakes:
            actual_conn = [b for b in connected_bakes if not b.get("is_group")]
            actual_dis = [b for b in disconnected_bakes if not b.get("is_group")]

            modifiers_data.append({
                "modifier_name": mod.name,
                "is_enabled": mod.show_viewport,
                "connected_count": len(actual_conn),
                "disconnected_count": len(actual_dis),
                "bakes": all_mod_bakes,
            })

    return modifiers_data


get_object_bake_items = get_object_bake_list
