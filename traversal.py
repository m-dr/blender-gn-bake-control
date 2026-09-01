import bpy


def find_bake_nodes_in_tree(node_tree, prefix=""):
    """Recursively find all bake nodes in a node tree topologically."""
    if not node_tree:
        return []

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

    results = []
    for node in ordered_nodes:
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


def get_object_bake_list(obj):
    """Return a clean list of modifiers and all their bake nodes for the active object."""
    if not obj or not hasattr(obj, "modifiers"):
        return []

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
                mod_items.append({
                    "name": item["name"],
                    "path": item["path"],
                    "node_name": node.name,
                    "tree_name": item["tree"].name if item["tree"] else "",
                    "bake_id": b_item.bake_id,
                    "mode": getattr(b_item, "bake_mode", "STILL"),
                    "has_cache": has_cache,
                })

        # Include any remaining bakes (e.g. simulation zone outputs)
        for b_item in unmapped_bakes:
            node = getattr(b_item, "node", None)
            node_name = node.label if (node and node.label) else (node.name if node else f"Bake #{b_item.bake_id}")
            has_cache = bool(getattr(b_item, "data_blocks", None) and len(b_item.data_blocks) > 0)
            mod_items.append({
                "name": node_name,
                "path": node_name,
                "node_name": node.name if node else "",
                "tree_name": mod.node_group.name if mod.node_group else "",
                "bake_id": b_item.bake_id,
                "mode": getattr(b_item, "bake_mode", "STILL"),
                "has_cache": has_cache,
            })

        if mod_items:
            modifiers_data.append({
                "modifier_name": mod.name,
                "bakes": mod_items,
            })

    return modifiers_data


get_object_bake_items = get_object_bake_list
