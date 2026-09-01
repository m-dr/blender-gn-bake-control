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

    mod_data = get_object_bake_list(obj, scene=context.scene, show_disconnected=show_disconnected)

    # Toolbar row with Disconnected nodes filter toggle
    row_tools = layout.row(align=True)
    if state:
        row_tools.prop(
            state,
            "show_disconnected",
            text="Show Disconnected / Stale",
            icon='HIDE_OFF' if state.show_disconnected else 'HIDE_ON'
        )

    if not mod_data:
        box = layout.box()
        box.label(text="No Geometry Nodes bake nodes on object.", icon='INFO')
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

        count_label = f"({conn_count} Active" + (f", {dis_count} Disc)" if dis_count > 0 else ")")
        head.label(text=count_label)

        # Jump to modifier in Node Editor button
        op_mod_nav = head.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
        op_mod_nav.modifier_name = mod_name

        # List each bake node
        for b in bakes:
            row = box.row(align=True)

            is_conn = b.get("is_connected", True)
            is_muted = b.get("is_muted", False)

            if not is_conn or is_muted:
                row.active = False

            # Proportional split: ~68% for node identifier, ~32% for right-aligned frame info
            split = row.split(factor=0.68, align=True)

            # Left section: Status + Jump + Node Path
            left = split.row(align=True)
            icon = 'CHECKMARK' if b["has_cache"] else 'RADIOBUT_OFF'
            left.label(text="", icon=icon)

            if b.get("node_name"):
                op_node_nav = left.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_node_nav.modifier_name = mod_name
                op_node_nav.node_tree_name = b.get("tree_name", "")
                op_node_nav.node_name = b.get("node_name", "")
            else:
                left.label(text="", icon='BLANK1')

            node_icon = 'AUTO' if b.get("is_simulation") else 'PHYSICS'
            display_text = b["path"]
            if not is_conn:
                display_text += " [Disc]"
            elif is_muted:
                display_text += " [Muted]"

            left.label(text=display_text, icon=node_icon)

            # Right section: Right-aligned compact frame info
            right = split.row(align=True)
            right.alignment = 'RIGHT'
            frame_icon = 'IMAGE_DATA' if b["mode"] == 'STILL' else 'TIME'
            right.label(text=b["frame_info"], icon=frame_icon)


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
