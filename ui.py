import bpy
from bpy.types import Panel

from .traversal import get_object_bake_list
from .preferences import get_preferences


def draw_gn_bake_ui(layout, context):
    obj = context.active_object
    if not obj:
        layout.label(text="Select an object to inspect bakes", icon='INFO')
        return

    state = getattr(obj, "gn_bake_state", None)
    show_disconnected = state.show_disconnected if state else True
    flatten_hierarchy = state.flatten_hierarchy if state else False
    collapsed_groups = set(state.collapsed_groups.split(";")) if (state and state.collapsed_groups) else set()

    mod_data = get_object_bake_list(obj, scene=context.scene, show_disconnected=show_disconnected)

    # Toolbar row with Filter and Flatten Hierarchy toggles
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

            # Skip children of collapsed groups when in hierarchical view
            if not flatten_hierarchy and skip_below_depth is not None:
                if b.get("depth", 0) > skip_below_depth:
                    continue
                else:
                    skip_below_depth = None

            group_key = f"{b.get('group_name', '')}::{b.get('name')}"
            full_key = f"{mod_name}::{group_key}"
            is_collapsed = full_key in collapsed_groups

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

                op_grp_nav = grp_row.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_grp_nav.modifier_name = mod_name
                op_grp_nav.node_tree_name = b.get("tree_name", "")
                op_grp_nav.node_name = b.get("node_name", "")

                if is_collapsed:
                    skip_below_depth = depth
                continue

            # 2. Node Item Row
            row = box.row(align=True)
            row.scale_y = 0.9

            if not is_conn:
                row.active = False

            # Proportional split: Left (Indentation + Status + Jump + Stage/Node), Right (Frame + Bake + Clear)
            split = row.split(factor=0.58, align=True)

            # Left section (dimmed visually if muted or disconnected)
            left = split.row(align=True)
            if is_muted or not is_conn:
                left.active = False

            # Exact icon-proportional indentation
            for _ in range(depth):
                left.label(text="", icon='BLANK1')

            # Cache status indicator
            icon = 'CHECKMARK' if b["has_cache"] else 'RADIOBUT_OFF'
            left.label(text="", icon=icon)

            # Compact right arrow navigate & frame node button
            if b.get("node_name"):
                op_node_nav = left.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_node_nav.modifier_name = mod_name
                op_node_nav.node_tree_name = b.get("tree_name", "")
                op_node_nav.node_name = b.get("node_name", "")
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

            # Right section: Right-aligned Frame info + Action buttons (Active & functional)
            right = split.row(align=True)
            right.alignment = 'RIGHT'
            right.active = True

            frame_icon = 'IMAGE_DATA' if b["mode"] == 'STILL' else 'TIME'
            right.label(text=b["frame_info"], icon=frame_icon)

            # Bake action button (Text)
            bake_id = b.get("bake_id", 0)
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
