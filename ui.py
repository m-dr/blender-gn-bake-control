import json
import bpy
from bpy.types import Panel

from .traversal import get_object_bake_list
from .preferences import get_preferences
from .operators import ACTIVE_BATCH_STATE


def draw_gn_bake_ui(layout, context):
    obj = context.active_object
    if not obj:
        layout.label(text="Select an object to inspect bakes", icon='INFO')
        return

    state = getattr(obj, "gn_bake_state", None)
    show_disconnected = state.show_disconnected if state else True
    flatten_hierarchy = state.flatten_hierarchy if state else False
    show_baked_range = state.show_baked_range if state else True
    show_target_range = state.show_target_range if state else True
    show_stats = state.show_stats if state else False
    collapsed_groups = set(state.collapsed_groups.split(";")) if (state and state.collapsed_groups) else set()

    is_batch_baking = bool(ACTIVE_BATCH_STATE.get("is_baking") and ACTIVE_BATCH_STATE.get("object_name") == obj.name)
    batch_status = ACTIVE_BATCH_STATE.get("status", {}) if is_batch_baking else {}

    # Detect active selected node in Node Editor space
    active_editor_node = None
    active_editor_tree = None
    if hasattr(context, "screen") and context.screen:
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                sp = area.spaces.active
                if sp and sp.node_tree:
                    curr_t = sp.path[-1].node_tree if (hasattr(sp, "path") and len(sp.path) > 0 and getattr(sp.path[-1], "node_tree", None)) else sp.node_tree
                    if curr_t and getattr(curr_t.nodes, "active", None):
                        active_editor_tree = curr_t
                        active_editor_node = curr_t.nodes.active
                break

    mod_data = get_object_bake_list(obj, scene=context.scene, show_disconnected=show_disconnected)

    # 1. Toolbar: 2 tidy rows (Filter & Flatten, then Column toggles)
    row_tools1 = layout.row(align=True)
    if state:
        row_tools1.prop(
            state,
            "show_disconnected",
            text="Show Disc/Muted",
            icon='HIDE_OFF' if state.show_disconnected else 'HIDE_ON'
        )
        row_tools1.prop(
            state,
            "flatten_hierarchy",
            text="Flatten",
            icon='ALIGN_JUSTIFY' if state.flatten_hierarchy else 'OUTLINER'
        )

    row_tools2 = layout.row(align=True)
    if state:
        row_tools2.prop(
            state,
            "show_baked_range",
            text="Baked",
            icon='CHECKMARK' if state.show_baked_range else 'RESTRICT_VIEW_ON'
        )
        row_tools2.prop(
            state,
            "show_target_range",
            text="Target",
            icon='PREVIEW_RANGE' if state.show_target_range else 'RESTRICT_VIEW_ON'
        )
        row_tools2.prop(
            state,
            "show_stats",
            text="Stats",
            icon='INFO'
        )

    # 2. Permanent Static Frame Policy Row (Always shown)
    if state:
        row_stat = layout.row(align=True)
        row_stat.scale_y = 0.9
        row_stat.label(text="Static Frame:")
        row_stat.prop(state, "static_bake_mode", text="")
        if state.static_bake_mode == 'GLOBAL':
            row_stat.prop(state, "static_global_frame", text="Frame")

    # 3. Batch Operations row: Rebake Stale, Clear Stale, (Re)bake All, Clear All
    row_batch = layout.row(align=True)
    row_batch.scale_y = 1.05

    op_rebake_stale = row_batch.operator("object.gn_bake_batch_action", text="Rebake Stale", icon='FILE_REFRESH')
    op_rebake_stale.action = 'REBAKE_STALE'

    op_clear_stale = row_batch.operator("object.gn_bake_batch_action", text="Clear Stale", icon='TRASH')
    op_clear_stale.action = 'CLEAR_STALE'

    op_bake_all = row_batch.operator("object.gn_bake_batch_action", text="(Re)bake All", icon='RENDER_STILL')
    op_bake_all.action = 'BAKE_ALL'

    op_clear_all = row_batch.operator("object.gn_bake_batch_action", text="Clear All", icon='TRASH')
    op_clear_all.action = 'CLEAR_ALL'

    if not mod_data:
        box = layout.box()
        box.label(text="No active Geometry Nodes bakes on object.", icon='INFO')
        return

    for entry in mod_data:
        mod_name = entry["modifier_name"]
        is_enabled = entry.get("is_enabled", True)
        bakes = entry["bakes"]
        conn_count = entry.get("connected_count", len(bakes))
        dis_count = entry.get("disconnected_count", 0)

        box = layout.box()
        box.active = is_enabled

        # Modifier header
        head = box.row(align=True)
        mod_icon = 'NODETREE' if is_enabled else 'RESTRICT_VIEW_ON'
        head.label(text=f"{mod_name}", icon=mod_icon)

        count_label = f"({conn_count} Active" + (f", {dis_count} Disc/Muted)" if dis_count > 0 else ")")
        head.label(text=count_label)

        # Jump to modifier in Node Editor button
        op_mod_nav = head.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
        op_mod_nav.modifier_name = mod_name

        # Track collapsed group hierarchy depth
        skip_below_depth = None

        for b in bakes:
            # When Flatten Hierarchy is active, hide group header rows
            if flatten_hierarchy and b.get("is_group"):
                continue

            depth = 0 if flatten_hierarchy else b.get("depth", 0)
            is_conn = b.get("is_connected", True)
            is_muted = b.get("is_muted", False)
            node = b.get("node")
            tree = b.get("tree")
            bake_id = b.get("bake_id", 0)

            # Check if this node is actively selected in Node Editor
            is_selected = bool(
                node and active_editor_node and node == active_editor_node and
                (tree == active_editor_tree or not active_editor_tree) and
                getattr(node, "select", False)
            )

            # Skip children of collapsed groups when in hierarchical view
            if not flatten_hierarchy and skip_below_depth is not None:
                if b.get("depth", 0) > skip_below_depth:
                    continue
                else:
                    skip_below_depth = None

            group_key = f"{b.get('group_name', '')}::{b.get('name')}"
            full_key = f"{mod_name}::{group_key}"
            is_collapsed = full_key in collapsed_groups

            chain_json = json.dumps(b.get("group_chain", []))

            # 1. Group Folder Header Row (Hierarchical view only)
            if b.get("is_group"):
                grp_row = box.row(align=True)
                grp_row.scale_y = 0.85

                if not is_conn or is_muted:
                    grp_row.active = False

                # Exact icon-proportional indentation
                for _ in range(depth):
                    grp_row.label(text="", icon='BLANK1')

                # Expand / Collapse disclosure triangle button
                op_toggle = grp_row.operator(
                    "object.gn_bake_toggle_group",
                    text="",
                    icon='DISCLOSURE_TRI_RIGHT' if is_collapsed else 'DISCLOSURE_TRI_DOWN',
                    emboss=False
                )
                op_toggle.modifier_name = mod_name
                op_toggle.group_key = group_key

                grp_icon = 'RESTRICT_SELECT_OFF' if is_selected else ('RESTRICT_VIEW_ON' if is_muted else 'NODETREE')
                grp_label = f"[{b['num_tag']}]  {b['name']}" + (" [Muted]" if is_muted else "")
                grp_row.label(text=grp_label, icon=grp_icon)

                op_grp_nav = grp_row.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_grp_nav.modifier_name = mod_name
                op_grp_nav.node_tree_name = b.get("tree_name", "")
                op_grp_nav.node_name = b.get("node_name", "")
                op_grp_nav.group_chain_json = chain_json

                if is_collapsed:
                    skip_below_depth = depth
                continue

            # 2. Node Item Row
            row = box.row(align=True)
            row.scale_y = 0.9

            if not is_conn:
                row.active = False

            # Calculate dynamic split factor based on active right-hand columns
            active_cols_count = (1 if show_baked_range else 0) + (1 if show_target_range else 0) + (1 if show_stats else 0)
            if active_cols_count == 3:
                split_factor = 0.30
            elif active_cols_count == 2:
                split_factor = 0.38
            elif active_cols_count == 1:
                split_factor = 0.48
            else:
                split_factor = 0.60

            split_main = row.split(factor=split_factor, align=True)

            # Left section (dimmed visually if muted or disconnected)
            left = split_main.row(align=True)
            if is_muted or not is_conn:
                left.active = False

            # Exact icon-proportional indentation
            for _ in range(depth):
                left.label(text="", icon='BLANK1')

            # 4-State cache status indicator (UNBAKED: RADIOBUT_OFF, INTERRUPTED: CANCEL, STALE: FILE_REFRESH, BAKED: CHECKMARK)
            if is_batch_baking and bake_id in batch_status:
                b_st = batch_status[bake_id]
                if b_st == 'PENDING':
                    icon = 'TIME'
                elif b_st == 'CURRENT':
                    icon = 'RESTRICT_SELECT_OFF'
                else:
                    icon = 'CHECKMARK'
            else:
                icon = b.get("status_icon", 'RADIOBUT_OFF')

            left.label(text="", icon=icon)

            # Compact right arrow navigate & frame node button
            if b.get("node_name"):
                op_node_nav = left.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_node_nav.modifier_name = mod_name
                op_node_nav.node_tree_name = b.get("tree_name", "")
                op_node_nav.node_name = b.get("node_name", "")
                op_node_nav.group_chain_json = chain_json
            else:
                left.label(text="", icon='BLANK1')

            # Node display name + Simulation / Mute / Type / Selected icon in fixed slot
            if is_selected:
                node_icon = 'RESTRICT_SELECT_OFF'
            elif is_muted:
                node_icon = 'RESTRICT_VIEW_ON'
            elif b.get("is_simulation"):
                node_icon = 'AUTO'
            else:
                node_icon = 'PHYSICS'

            # Display name (include group prefix if in flattened view and inside group)
            display_name = b["name"]
            if flatten_hierarchy and b.get("group_name"):
                display_name = f"{b['group_name']} > {b['name']}"

            display_text = f"[{b['num_tag']}]  {display_name}" if b.get("num_tag") else display_name

            if not is_conn:
                display_text += " [Disc]"
            elif is_muted:
                display_text += " [Muted]"

            left.label(text=display_text, icon=node_icon)

            # Right section: Fixed-width proportional sub-splits for perfect vertical column alignment
            right = split_main.row(align=True)
            right.active = True

            baked_text = b.get("baked_frame_info", "-")
            target_text = b.get("target_frame_info", "-")
            dur_text = b.get("duration_str", "-")
            is_still = b["mode"] == 'STILL'

            # Helper for action buttons [Bake] [Trash]
            def draw_ops(container):
                if bake_id:
                    op_bake = container.operator("object.gn_bake_single_action", text="Bake")
                    op_bake.action = 'BAKE'
                    op_bake.modifier_name = mod_name
                    op_bake.bake_id = bake_id

                    sub_clear = container.row(align=True)
                    sub_clear.enabled = b["has_cache"]
                    op_clear = sub_clear.operator("object.gn_bake_single_action", text="", icon='TRASH')
                    op_clear.action = 'CLEAR'
                    op_clear.modifier_name = mod_name
                    op_clear.bake_id = bake_id
                else:
                    container.label(text="")

            # Layout sub-split configurations:
            if show_baked_range and show_target_range and show_stats:
                c_b = right.split(factor=0.28, align=True)
                c_b.label(text=baked_text)

                c_t = c_b.split(factor=0.38, align=True)
                c_t.label(text=target_text)

                c_ops = c_t.split(factor=0.50, align=True)
                draw_ops(c_ops)

                c_dur = c_ops.row(align=True)
                c_dur.alignment = 'RIGHT'
                c_dur.label(text=dur_text)

            elif show_baked_range and show_target_range and not show_stats:
                c_b = right.split(factor=0.33, align=True)
                c_b.label(text=baked_text)

                c_t = c_b.split(factor=0.48, align=True)
                c_t.label(text=target_text)

                c_ops = c_t.row(align=True)
                draw_ops(c_ops)

            elif show_baked_range and not show_target_range and show_stats:
                c_b = right.split(factor=0.38, align=True)
                c_b.label(text=baked_text)

                c_ops = c_b.split(factor=0.58, align=True)
                draw_ops(c_ops)

                c_dur = c_ops.row(align=True)
                c_dur.alignment = 'RIGHT'
                c_dur.label(text=dur_text)

            elif not show_baked_range and show_target_range and show_stats:
                c_t = right.split(factor=0.38, align=True)
                c_t.label(text=target_text)

                c_ops = c_t.split(factor=0.58, align=True)
                draw_ops(c_ops)

                c_dur = c_ops.row(align=True)
                c_dur.alignment = 'RIGHT'
                c_dur.label(text=dur_text)

            elif show_baked_range and not show_target_range and not show_stats:
                c_b = right.split(factor=0.45, align=True)
                c_b.label(text=baked_text)

                c_ops = c_b.row(align=True)
                draw_ops(c_ops)

            elif not show_baked_range and show_target_range and not show_stats:
                c_t = right.split(factor=0.45, align=True)
                c_t.label(text=target_text)

                c_ops = c_t.row(align=True)
                draw_ops(c_ops)

            elif not show_baked_range and not show_target_range and show_stats:
                c_ops = right.split(factor=0.65, align=True)
                draw_ops(c_ops)

                c_dur = c_ops.row(align=True)
                c_dur.alignment = 'RIGHT'
                c_dur.label(text=dur_text)

            else:
                c_ops = right.row(align=True)
                draw_ops(c_ops)


class DATA_PT_gn_bake_control(Panel):
    bl_idname = "DATA_PT_gn_bake_control"
    bl_label = "GN Bake Control (DEV)"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "modifier"
    bl_order = -100

    @classmethod
    def poll(cls, context):
        prefs = get_preferences(context)
        if prefs and not prefs.show_in_modifier_stack:
            return False
        return context.active_object is not None

    def draw(self, context):
        draw_gn_bake_ui(self.layout, context)


class VIEW3D_PT_gn_bake_control(Panel):
    bl_idname = "VIEW3D_PT_gn_bake_control"
    bl_label = "GN Bake Control (DEV)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "GN Bake (DEV)"

    @classmethod
    def poll(cls, context):
        prefs = get_preferences(context)
        if prefs and not prefs.show_in_3dview_sidebar:
            return False
        return context.active_object is not None

    def draw(self, context):
        draw_gn_bake_ui(self.layout, context)


classes = (
    DATA_PT_gn_bake_control,
    VIEW3D_PT_gn_bake_control,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
