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
    show_frame_range = state.show_frame_range if state else True
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

    # 1. Toolbar row: Filter, Flatten, Frames, and Stats toggles
    row_tools = layout.row(align=True)
    if state:
        row_tools.prop(
            state,
            "show_disconnected",
            text="Show Disc/Muted",
            icon='HIDE_OFF' if state.show_disconnected else 'HIDE_ON'
        )
        row_tools.prop(
            state,
            "flatten_hierarchy",
            text="Flatten",
            icon='ALIGN_JUSTIFY' if state.flatten_hierarchy else 'OUTLINER'
        )
        row_tools.prop(
            state,
            "show_frame_range",
            text="Frames",
            icon='TIME' if state.show_frame_range else 'RESTRICT_VIEW_ON'
        )
        row_tools.prop(
            state,
            "show_stats",
            text="Stats",
            icon='INFO'
        )

    # 2. Permanent Static Frame Policy Row (Always shown)
    if state:
        row_stat_settings = layout.row(align=True)
        row_stat_settings.scale_y = 0.9
        row_stat_settings.prop(state, "static_bake_mode", text="Static Frame")
        if state.static_bake_mode == 'GLOBAL':
            row_stat_settings.prop(state, "static_global_frame", text="Frame")

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

                grp_icon = 'RESTRICT_VIEW_ON' if is_muted else 'NODETREE'
                grp_label = f"[{b['num_tag']}]  {b['name']}" + (" [Muted]" if is_muted else "")
                grp_row.label(text=grp_label, icon=grp_icon)

                # Active selection indicator icon if group node is selected in editor
                if is_selected:
                    grp_row.label(text="", icon='RESTRICT_SELECT_OFF')

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

            # Proportional split: Left (Indentation + Status + Jump + Stage/Node), Right (Frame + Stats + Bake + Clear)
            split_factor = 0.50 if show_stats else (0.58 if show_frame_range else 0.68)
            split = row.split(factor=split_factor, align=True)

            # Left section (dimmed visually if muted or disconnected)
            left = split.row(align=True)
            if is_muted or not is_conn:
                left.active = False

            # Exact icon-proportional indentation
            for _ in range(depth):
                left.label(text="", icon='BLANK1')

            # Status indicator icon:
            # During active batch baking: Orange (Pending) -> Yellow (Current) -> Green (Done)
            if is_batch_baking and bake_id in batch_status:
                b_st = batch_status[bake_id]
                if b_st == 'PENDING':
                    icon = 'RADIOBUT_ON'  # Orange pending
                elif b_st == 'CURRENT':
                    icon = 'RESTRICT_SELECT_OFF'  # Yellow active indicator
                else:
                    icon = 'CHECKMARK'  # Green done
            else:
                icon = b.get("status_icon", 'CHECKMARK' if b.get("has_cache") else 'RADIOBUT_OFF')

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

            # Node display name + Simulation / Mute / Type icon
            if is_muted:
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

            # Active selection indicator icon if selected in editor
            if is_selected:
                left.label(text="", icon='RESTRICT_SELECT_OFF')

            # Right section: Frame info + Action buttons + Far right Stats duration
            right = split.row(align=True)
            right.alignment = 'RIGHT'
            right.active = True

            # Frame info column (toggled via Frames button)
            if show_frame_range:
                frame_icon = 'IMAGE_DATA' if b["mode"] == 'STILL' else 'TIME'
                right.label(text=b["frame_info"], icon=frame_icon)

            # Bake action button (Text)
            if bake_id:
                op_bake = right.operator("object.gn_bake_single_action", text="Bake")
                op_bake.action = 'BAKE'
                op_bake.modifier_name = mod_name
                op_bake.bake_id = bake_id

                # Clear cache action button (Trash can icon)
                sub_clear = right.row(align=True)
                sub_clear.enabled = b["has_cache"]
                op_clear = sub_clear.operator("object.gn_bake_single_action", text="", icon='TRASH')
                op_clear.action = 'CLEAR'
                op_clear.modifier_name = mod_name
                op_clear.bake_id = bake_id

            # Far right Stats column (Uniform width, plain text duration without icon)
            if show_stats:
                dur_col = right.row(align=True)
                dur_col.alignment = 'RIGHT'
                dur_text = b.get("duration_str", "-")
                dur_col.label(text=dur_text)


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
