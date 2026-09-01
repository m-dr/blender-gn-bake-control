import os
import re
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


def compute_tree_bake_stages(
    node_tree,
    depth=0,
    group_hierarchy=None,
    group_chain=None,
    is_parent_connected=True,
    is_parent_muted=False,
    parent_upstream_nodes=None
):
    """
    Compute DAG longest-path topological execution stages, clean local number tags, upstream dependencies,
    and exact breadcrumb navigation chains.
    Returns (connected_items, disconnected_items).
    """
    if not node_tree:
        return [], []

    if group_hierarchy is None:
        group_hierarchy = []
    if group_chain is None:
        group_chain = []
    if parent_upstream_nodes is None:
        parent_upstream_nodes = []

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

    interesting_set = set(interesting_nodes)

    # Full upstream DAG dependency closure
    upstream_dependencies = defaultdict(set)
    for n in interesting_nodes:
        queue = list(upstream_adj.get(n, []))
        visited_up = set(queue)
        while queue:
            curr = queue.pop(0)
            if curr in interesting_set and curr != n:
                upstream_dependencies[n].add(curr)
            for prev in upstream_adj.get(curr, []):
                if prev in reachable and prev not in visited_up:
                    visited_up.add(prev)
                    queue.append(prev)

    # Topological execution stages based on upstream dependencies
    stages = {}
    for n in interesting_nodes:
        up_deps = upstream_dependencies[n]
        if not up_deps:
            stages[n] = 1
        else:
            known_stages = [stages[u] for u in up_deps if u in stages]
            stages[n] = max(known_stages) + 1 if known_stages else 1

    by_stage = defaultdict(list)
    for n in interesting_nodes:
        by_stage[stages[n]].append(n)

    connected_items = []
    max_stage = max(by_stage.keys()) if by_stage else 0

    for stage_num in sorted(by_stage.keys()):
        stage_nodes = by_stage[stage_num]
        stage_nodes.sort(key=lambda n: (n.location.x, -n.location.y))
        has_siblings = len(stage_nodes) > 1

        for idx, node in enumerate(stage_nodes, 1):
            num_tag = f"{stage_num}.{idx}" if has_siblings else f"{stage_num}"
            name = node.label if node.label else node.name
            node_muted = is_parent_muted or bool(getattr(node, "mute", False))
            all_upstream = list(upstream_dependencies[node]) + parent_upstream_nodes

            if node.type in ('BAKE', 'SIMULATION_OUTPUT'):
                connected_items.append({
                    "name": name,
                    "num_tag": num_tag,
                    "group_name": " > ".join(group_hierarchy) if group_hierarchy else "",
                    "depth": depth,
                    "node": node,
                    "tree": node_tree,
                    "group_chain": list(group_chain),
                    "is_group": False,
                    "is_connected": is_parent_connected,
                    "is_muted": node_muted,
                    "is_simulation": node.type == 'SIMULATION_OUTPUT',
                    "upstream_nodes": all_upstream,
                })
            elif node.type == 'GROUP' and getattr(node, "node_tree", None):
                group_name = node.label if node.label else node.node_tree.name
                sub_group_chain = group_chain + [(node.node_tree.name, node.name)]
                sub_conn, sub_dis = compute_tree_bake_stages(
                    node.node_tree,
                    depth=depth + 1,
                    group_hierarchy=group_hierarchy + [group_name],
                    group_chain=sub_group_chain,
                    is_parent_connected=is_parent_connected,
                    is_parent_muted=node_muted,
                    parent_upstream_nodes=all_upstream,
                )
                connected_items.append({
                    "name": group_name,
                    "num_tag": num_tag,
                    "group_name": " > ".join(group_hierarchy) if group_hierarchy else "",
                    "depth": depth,
                    "node": node,
                    "tree": node_tree,
                    "group_chain": list(group_chain),
                    "is_group": True,
                    "group_tree": node.node_tree,
                    "is_connected": is_parent_connected,
                    "is_muted": node_muted,
                    "is_simulation": False,
                    "upstream_nodes": all_upstream,
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
        num_tag = f"{max_stage + i}"
        name = dn.label if dn.label else dn.name
        disconnected_items.append({
            "name": name,
            "num_tag": num_tag,
            "group_name": " > ".join(group_hierarchy) if group_hierarchy else "",
            "depth": depth,
            "node": dn,
            "tree": node_tree,
            "group_chain": list(group_chain),
            "is_group": False,
            "is_connected": False,
            "is_muted": dn.mute if hasattr(dn, "mute") else False,
            "is_simulation": dn.type == 'SIMULATION_OUTPUT',
            "upstream_nodes": [],
        })

    return connected_items, disconnected_items


def check_bake_cache_info(obj, mod, bake_item, timestamps_dict=None):
    """
    Accurately check cache presence and modification timestamp across
    both UI-triggered bakes and native Node Editor bakes.
    Returns (has_cache: bool, timestamp: float).
    """
    if not bake_item:
        return False, 0.0

    key = f"{mod.name}::{bake_item.bake_id}"
    recorded_ts = timestamps_dict.get(key, 0.0) if timestamps_dict else 0.0

    # 1. Check internal data blocks
    if getattr(bake_item, "data_blocks", None) and len(bake_item.data_blocks) > 0:
        return True, recorded_ts if recorded_ts > 0 else 1.0

    # 2. Check explicit disk directory
    dir_path = getattr(bake_item, "directory", "")
    if dir_path:
        abs_p = bpy.path.abspath(dir_path)
        if os.path.exists(abs_p):
            mtimes = []
            for root, _, files in os.walk(abs_p):
                for f in files:
                    try:
                        mtimes.append(os.path.getmtime(os.path.join(root, f)))
                    except Exception:
                        pass
            if mtimes:
                return True, max(max(mtimes), recorded_ts)
            elif os.path.exists(abs_p) and len(os.listdir(abs_p)) > 0:
                return True, recorded_ts if recorded_ts > 0 else 1.0

    # 3. Bi-directional scan for native Blender blendcache directory
    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        if blend_dir and os.path.exists(blend_dir):
            try:
                for entry in os.listdir(blend_dir):
                    if entry.startswith("blendcache_"):
                        cache_root = os.path.join(blend_dir, entry)
                        if os.path.isdir(cache_root):
                            for dirpath, _, filenames in os.walk(cache_root):
                                if os.path.basename(dirpath) == str(bake_item.bake_id):
                                    mtimes = []
                                    for sub_root, _, sub_files in os.walk(dirpath):
                                        for sf in sub_files:
                                            try:
                                                mtimes.append(os.path.getmtime(os.path.join(sub_root, sf)))
                                            except Exception:
                                                pass
                                    if mtimes:
                                        return True, max(max(mtimes), recorded_ts)
            except Exception:
                pass

    if recorded_ts > 0:
        return True, recorded_ts

    return False, 0.0


def scan_baked_frames(bake_item, mod=None, state=None):
    """
    Scans cache directory or blend data to determine the exact range of frames actually baked.
    Returns:
      (min_frame, max_frame): tuple of ints for animation
      single_frame: int for still
      None: if no cached frame files exist
    """
    if not bake_item:
        return None

    dir_path = getattr(bake_item, "directory", "")
    abs_p = bpy.path.abspath(dir_path) if dir_path else ""

    candidate_dirs = []
    if abs_p and os.path.exists(abs_p):
        candidate_dirs.append(abs_p)

    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        if blend_dir and os.path.exists(blend_dir):
            try:
                for entry in os.listdir(blend_dir):
                    if entry.startswith("blendcache_"):
                        cache_root = os.path.join(blend_dir, entry)
                        if os.path.isdir(cache_root):
                            for dirpath, _, _ in os.walk(cache_root):
                                if os.path.basename(dirpath) == str(bake_item.bake_id):
                                    candidate_dirs.append(dirpath)
            except Exception:
                pass

    frames = set()
    found_any_file = False

    for c_dir in candidate_dirs:
        for root, _, files in os.walk(c_dir):
            for f in files:
                found_any_file = True
                m = re.match(r'^(\d{4,6})_\d{4,6}\.(?:blob|json)$', f)
                if m:
                    frames.add(int(m.group(1)))
                else:
                    m2 = re.match(r'^(?:frame_)?(\d+)\.', f)
                    if m2:
                        try:
                            frames.add(int(m2.group(1)))
                        except Exception:
                            pass

    if frames:
        sorted_f = sorted(frames)
        return (sorted_f[0], sorted_f[-1])

    if getattr(bake_item, "data_blocks", None) and len(bake_item.data_blocks) > 0:
        found_any_file = True

    if found_any_file:
        rec = state.get_recorded_frame(mod.name, bake_item.bake_id) if (state and mod) else None
        if rec is not None:
            return rec
        return "SINGLE"

    return None


def check_bake_has_cache(bake_item):
    """Legacy compatibility helper."""
    if not bake_item:
        return False
    if getattr(bake_item, "data_blocks", None) and len(bake_item.data_blocks) > 0:
        return True
    if getattr(bake_item, "directory", ""):
        p = bpy.path.abspath(bake_item.directory)
        if os.path.exists(p) and len(os.listdir(p)) > 0:
            return True
    return False


def get_object_bake_list(obj, scene=None, show_disconnected=True):
    """
    Return all modifiers and their bake nodes in hierarchical DAG execution sequence
    with 3-state cache status (UNBAKED, BAKED, STALE), number badges, and metadata.
    """
    if not obj or not hasattr(obj, "modifiers"):
        return []

    if scene is None:
        scene = bpy.context.scene if hasattr(bpy, "context") and bpy.context else None

    scene_frame_current = scene.frame_current if scene else 1
    scene_frame_start = scene.frame_start if scene else 1
    scene_frame_end = scene.frame_end if scene else 250

    state = getattr(obj, "gn_bake_state", None)
    timestamps_dict = state.get_timestamps() if state else {}

    modifiers_data = []
    max_upstream_mod_bake_time = 0.0

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

        # First pass: collect node timestamps and cache presence
        node_timestamps = {}
        node_has_cache = {}

        for item in all_conn_items + all_dis_items:
            node = item.get("node")
            b_item = bake_by_node.get(node)
            has_c, ts = check_bake_cache_info(obj, mod, b_item, timestamps_dict)
            node_has_cache[node] = has_c
            node_timestamps[node] = ts

        # Groups take max timestamp of their child items
        for item in all_conn_items + all_dis_items:
            if item.get("is_group"):
                node = item.get("node")
                group_children = item.get("children", [])
                child_ts = [node_timestamps.get(c.get("node"), 0.0) for c in group_children if c.get("node")]
                if child_ts:
                    node_timestamps[node] = max(child_ts)

        # Track max bake time in this modifier to propagate to downstream modifiers
        current_mod_max_time = 0.0
        for ts in node_timestamps.values():
            if ts > current_mod_max_time:
                current_mod_max_time = ts

        def build_bake_info(item):
            node = item.get("node")
            b_item = bake_by_node.get(node)
            if b_item and b_item in unmapped_bakes:
                unmapped_bakes.remove(b_item)

            has_cache = node_has_cache.get(node, False)
            node_time = node_timestamps.get(node, 0.0)

            # Determine 3-state cache status: UNBAKED, BAKED, STALE
            if not has_cache:
                cache_state = 'UNBAKED'
                status_icon = 'RADIOBUT_OFF'
            else:
                is_stale = False
                # Check upstream nodes in DAG data flow
                for u_node in item.get("upstream_nodes", []):
                    u_time = node_timestamps.get(u_node, 0.0)
                    if u_time > node_time:
                        is_stale = True
                        break

                # Check if an upstream modifier in the stack was rebaked
                if not is_stale and max_upstream_mod_bake_time > node_time:
                    is_stale = True

                if is_stale:
                    cache_state = 'STALE'
                    status_icon = 'FILE_REFRESH'
                else:
                    cache_state = 'BAKED'
                    status_icon = 'CHECKMARK'

            mode = getattr(b_item, "bake_mode", "ANIMATION" if item.get("is_simulation") else "STILL")
            rec_frame = state.get_recorded_frame(mod.name, b_item.bake_id) if (state and b_item) else None
            duration_sec = state.get_bake_duration(mod.name, b_item.bake_id) if (state and b_item) else 0.0

            # 1. Target Frame / Range and Tooltip metadata
            if mode == 'STILL':
                if state and state.static_bake_mode == 'ORIGINAL':
                    target_f = rec_frame if rec_frame is not None else scene_frame_current
                    target_frame_info = f"{target_f}"
                    target_frame_tooltip = f"Original frame policy: Target frame {target_f}"
                elif state and state.static_bake_mode == 'GLOBAL':
                    target_frame_info = f"{state.static_global_frame}"
                    target_frame_tooltip = f"Global frame policy: Target frame {state.static_global_frame}"
                else:
                    target_frame_info = f"{scene_frame_current}"
                    target_frame_tooltip = f"Current frame policy: Target active timeline frame {scene_frame_current}"
                target_start_f = scene_frame_current
                target_end_f = scene_frame_current
            else:
                if b_item and getattr(b_item, "use_custom_simulation_frame_range", False):
                    target_start_f = b_item.frame_start
                    target_end_f = b_item.frame_end
                    target_frame_info = f"{target_start_f} – {target_end_f}"
                    target_frame_tooltip = f"Custom range set in node settings: {target_start_f} to {target_end_f}"
                else:
                    target_start_f = scene_frame_start
                    target_end_f = scene_frame_end
                    target_frame_info = f"{target_start_f} – {target_end_f}"
                    target_frame_tooltip = f"Scene timeline range: {target_start_f} to {target_end_f}"

            # 2. Currently Baked Range (actual files on disk/cache)
            cached_range = None
            is_interrupted = False
            if not has_cache:
                baked_frame_info = "-"
            else:
                if mode == 'STILL':
                    baked_frame = rec_frame if rec_frame is not None else scene_frame_current
                    baked_frame_info = f"{baked_frame}"
                else:
                    cached_range = scan_baked_frames(b_item, mod, state)
                    if isinstance(cached_range, tuple):
                        min_f, max_f = cached_range
                        baked_frame_info = f"{min_f}" if min_f == max_f else f"{min_f} – {max_f}"
                        if min_f > target_start_f or max_f < target_end_f:
                            is_interrupted = True
                    elif isinstance(cached_range, int):
                        baked_frame_info = f"{cached_range}"
                        if target_start_f != target_end_f:
                            is_interrupted = True
                    elif getattr(b_item, "use_custom_simulation_frame_range", False):
                        baked_frame_info = f"{b_item.frame_start} – {b_item.frame_end}"
                    else:
                        baked_frame_info = f"{scene_frame_start} – {scene_frame_end}"

            # 3. Determine 4-state cache status: UNBAKED, INTERRUPTED, STALE, BAKED
            if not has_cache:
                cache_state = 'UNBAKED'
                status_icon = 'RADIOBUT_OFF'
            elif is_interrupted:
                cache_state = 'INTERRUPTED'
                status_icon = 'CANCEL'
            else:
                is_stale = False
                # Check upstream nodes in DAG data flow
                for u_node in item.get("upstream_nodes", []):
                    u_time = node_timestamps.get(u_node, 0.0)
                    if u_time > node_time:
                        is_stale = True
                        break

                # Check if an upstream modifier in the stack was rebaked
                if not is_stale and max_upstream_mod_bake_time > node_time:
                    is_stale = True

                if is_stale:
                    cache_state = 'STALE'
                    status_icon = 'FILE_REFRESH'
                else:
                    cache_state = 'BAKED'
                    status_icon = 'CHECKMARK'

            frame_info = baked_frame_info if has_cache else target_frame_info
            duration_str = f"{duration_sec:.1f}s" if duration_sec > 0 else "-"

            return {
                "name": item["name"],
                "num_tag": item.get("num_tag", ""),
                "group_name": item.get("group_name", ""),
                "depth": item.get("depth", 0),
                "node": node,
                "tree": item.get("tree"),
                "node_name": node.name if node else "",
                "tree_name": item["tree"].name if item.get("tree") else "",
                "group_chain": item.get("group_chain", []),
                "bake_id": b_item.bake_id if b_item else 0,
                "mode": mode,
                "frame_info": frame_info,
                "baked_frame_info": baked_frame_info,
                "target_frame_info": target_frame_info,
                "target_frame_tooltip": target_frame_tooltip,
                "duration_str": duration_str,
                "duration_sec": duration_sec,
                "recorded_frame": rec_frame,
                "has_cache": has_cache,
                "cache_state": cache_state,
                "status_icon": status_icon,
                "bake_timestamp": node_time,
                "is_group": item.get("is_group", False),
                "is_connected": item.get("is_connected", True),
                "is_muted": item.get("is_muted", False),
                "is_simulation": item.get("is_simulation", False),
                "upstream_nodes": item.get("upstream_nodes", []),
                "bake_item": b_item,
            }

        connected_bakes = [build_bake_info(it) for it in all_conn_items]

        # Calculate max root stage for clean sequential disconnected numbering
        root_stages = []
        for b in connected_bakes:
            if b.get("depth", 0) == 0:
                tag = b.get("num_tag", "")
                if tag and "." not in tag:
                    try:
                        root_stages.append(int(tag))
                    except ValueError:
                        pass
                elif tag:
                    try:
                        root_stages.append(int(tag.split(".")[0]))
                    except ValueError:
                        pass
        max_root_stage = max(root_stages) if root_stages else len(connected_bakes)

        # Renumber disconnected items starting after max_root_stage
        disconnected_bakes = []
        for i, it in enumerate(all_dis_items, 1):
            info = build_bake_info(it)
            info["num_tag"] = f"{max_root_stage + i}"
            disconnected_bakes.append(info)

        # Remaining unmapped bakes in mod.bakes
        for b_item in unmapped_bakes:
            node = getattr(b_item, "node", None)
            node_name = node.label if (node and node.label) else (node.name if node else f"Bake #{b_item.bake_id}")
            has_cache, b_time = check_bake_cache_info(obj, mod, b_item, timestamps_dict)
            mode = getattr(b_item, "bake_mode", "STILL")
            rec_frame = state.get_recorded_frame(mod.name, b_item.bake_id) if state else None
            duration_sec = state.get_bake_duration(mod.name, b_item.bake_id) if state else 0.0

            if mode == 'STILL':
                display_frame = rec_frame if (has_cache and rec_frame is not None) else scene_frame_current
                frame_info = f"{display_frame}"
            else:
                if getattr(b_item, "use_custom_simulation_frame_range", False):
                    frame_info = f"{b_item.frame_start} – {b_item.frame_end} (Cust)"
                else:
                    frame_info = f"{scene_frame_start} – {scene_frame_end}"

            duration_str = f"{duration_sec:.1f}s" if duration_sec > 0 else "-"

            next_idx = max_root_stage + len(disconnected_bakes) + 1
            disconnected_bakes.append({
                "name": node_name,
                "num_tag": f"{next_idx}",
                "group_name": "",
                "depth": 0,
                "node": node,
                "tree": mod.node_group,
                "node_name": node.name if node else "",
                "tree_name": mod.node_group.name if mod.node_group else "",
                "group_chain": [],
                "bake_id": b_item.bake_id,
                "mode": mode,
                "frame_info": frame_info,
                "duration_str": duration_str,
                "duration_sec": duration_sec,
                "recorded_frame": rec_frame,
                "has_cache": has_cache,
                "cache_state": 'BAKED' if has_cache else 'UNBAKED',
                "status_icon": 'CHECKMARK' if has_cache else 'RADIOBUT_OFF',
                "bake_timestamp": b_time,
                "is_group": False,
                "is_connected": False,
                "is_muted": node.mute if node else False,
                "is_simulation": getattr(node, "type", "") == 'SIMULATION_OUTPUT',
                "bake_item": b_item,
            })

        # Update modifier-level timestamp for downstream modifiers
        if current_mod_max_time > max_upstream_mod_bake_time:
            max_upstream_mod_bake_time = current_mod_max_time

        # Separate active vs muted/stale for filtering
        actual_conn_active = [b for b in connected_bakes if not b.get("is_group") and not b.get("is_muted")]
        actual_conn_muted = [b for b in connected_bakes if not b.get("is_group") and b.get("is_muted")]
        actual_dis = [b for b in disconnected_bakes if not b.get("is_group")]

        total_stale_count = len(actual_dis) + len(actual_conn_muted)

        if not show_disconnected:
            visible_bakes = []
            for b in connected_bakes:
                if b.get("is_muted"):
                    continue
                if b.get("is_group"):
                    group_name = b.get("name")
                    has_active_child = any(
                        not child.get("is_muted") and not child.get("is_group") and group_name in child.get("group_name", "")
                        for child in connected_bakes
                    )
                    if not has_active_child:
                        continue
                visible_bakes.append(b)
        else:
            visible_bakes = connected_bakes + disconnected_bakes

        if visible_bakes or show_disconnected:
            modifiers_data.append({
                "modifier_name": mod.name,
                "is_enabled": mod.show_viewport,
                "connected_count": len(actual_conn_active),
                "disconnected_count": total_stale_count,
                "bakes": visible_bakes,
            })

    return modifiers_data


get_object_bake_items = get_object_bake_list
