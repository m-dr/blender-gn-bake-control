import bpy
from .properties import get_or_create_bake_setting


def get_bake_nodes_in_tree(node_tree, prefix=""):
    """Traverse a node tree topologically and recursively yield (prefix, label, node, node_tree)."""
    if not node_tree:
        return []

    in_degree = {n: 0 for n in node_tree.nodes}
    adj = {n: [] for n in node_tree.nodes}

    for link in node_tree.links:
        if link.is_valid and link.from_node in in_degree and link.to_node in in_degree:
            adj[link.from_node].append(link.to_node)
            in_degree[link.to_node] += 1

    # Roots: in_degree == 0, sorted by X location left-to-right, then top-to-bottom
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

    # Catch any cyclic or unconnected nodes
    for n in node_tree.nodes:
        if n not in ordered_nodes:
            ordered_nodes.append(n)

    bakes = []
    for node in ordered_nodes:
        curr_label = node.label if node.label else node.name
        if node.type == 'BAKE':
            bakes.append((prefix, curr_label, node, node_tree))
        elif node.type == 'GROUP' and getattr(node, 'node_tree', None):
            sub_prefix = f"{prefix}{curr_label} > " if prefix else f"{curr_label} > "
            sub_bakes = get_bake_nodes_in_tree(node.node_tree, prefix=sub_prefix)
            bakes.extend(sub_bakes)

    return bakes


def bake_has_cache(bake_item):
    """Check if bake item has cached data."""
    try:
        if hasattr(bake_item, "data_blocks") and len(bake_item.data_blocks) > 0:
            return True
        # For disk caches or packed items where data_blocks collection might not list immediately,
        # we can also check if directory is set or if cache files exist
        if getattr(bake_item, "bake_target", "") == 'DISK' and getattr(bake_item, "directory", ""):
            import os
            cache_dir = bpy.path.abspath(bake_item.directory)
            if os.path.exists(cache_dir) and os.listdir(cache_dir):
                return True
    except Exception:
        pass
    return False


def get_object_bake_items(obj, filter_text="", missing_only=False):
    """
    Traverse all Geometry Nodes modifiers on the object in stack order.
    Returns a list of dicts with all metadata, sorted topologically.
    """
    if not obj or not hasattr(obj, "modifiers"):
        return []

    items = []
    for mod in obj.modifiers:
        if mod.type != 'NODES' or not mod.node_group or not hasattr(mod, "bakes"):
            continue

        # Map nodes to bake items in modifier
        bake_item_by_node = {}
        bake_items_unmapped = list(mod.bakes)

        for b in mod.bakes:
            if b.node:
                bake_item_by_node[b.node] = b

        # Topological traversal of node tree
        ordered_tree_bakes = get_bake_nodes_in_tree(mod.node_group)

        for prefix, label, node, ntree in ordered_tree_bakes:
            b_item = bake_item_by_node.get(node)
            if b_item:
                if b_item in bake_items_unmapped:
                    bake_items_unmapped.remove(b_item)

                has_cached_data = bake_has_cache(b_item)
                if missing_only and has_cached_data:
                    continue

                display_name = f"{prefix}{label}" if prefix else label
                if filter_text:
                    ft = filter_text.lower()
                    if ft not in display_name.lower() and ft not in mod.name.lower():
                        continue

                setting = get_or_create_bake_setting(obj, mod.name, b_item.bake_id, node.name)

                items.append({
                    "object": obj,
                    "modifier": mod,
                    "modifier_name": mod.name,
                    "bake_item": b_item,
                    "bake_id": b_item.bake_id,
                    "node": node,
                    "node_name": node.name,
                    "node_label": label,
                    "group_path": prefix.rstrip(" > "),
                    "display_name": display_name,
                    "node_tree": ntree,
                    "bake_mode": b_item.bake_mode,
                    "has_cache": has_cached_data,
                    "setting": setting,
                    "is_simulation": False,
                })

        # Append any remaining unmapped bakes (e.g., simulation zone bakes)
        for b_item in bake_items_unmapped:
            node = getattr(b_item, "node", None)
            node_name = node.name if node else f"Bake_{b_item.bake_id}"
            label = node.label if (node and node.label) else node_name

            has_cached_data = bake_has_cache(b_item)
            if missing_only and has_cached_data:
                continue

            if filter_text:
                ft = filter_text.lower()
                if ft not in label.lower() and ft not in mod.name.lower():
                    continue

            setting = get_or_create_bake_setting(obj, mod.name, b_item.bake_id, node_name)

            items.append({
                "object": obj,
                "modifier": mod,
                "modifier_name": mod.name,
                "bake_item": b_item,
                "bake_id": b_item.bake_id,
                "node": node,
                "node_name": node_name,
                "node_label": label,
                "group_path": "",
                "display_name": label,
                "node_tree": mod.node_group,
                "bake_mode": b_item.bake_mode,
                "has_cache": has_cached_data,
                "setting": setting,
                "is_simulation": getattr(node, "type", "") == 'SIMULATION_OUTPUT' or "sim" in node_name.lower(),
            })

    return items
