import bpy
from bpy.types import Panel

from .traversal import get_object_bake_items
from .properties import find_bake_setting
from .preferences import get_preferences


def draw_gn_bake_ui(layout, context, is_npanel=False):
    obj = context.active_object
    if not obj:
        layout.label(text="Select an object to inspect bakes", icon='INFO')
        return

    state = getattr(obj, "gn_bake_state", None)
    filter_text = state.filter_text if state else ""
    missing_only = state.show_missing_only if state else False

    items = get_object_bake_items(obj, filter_text=filter_text, missing_only=missing_only)

    # 1. Global Batch Actions Toolbar
    col_top = layout.column(align=True)
    row_batch = col_top.row(align=True)
    row_batch.scale_y = 1.2

    op_bake = row_batch.operator("object.gn_bake_batch", text="Bake Selected", icon='PHYSICS')
    op_bake.mode = 'BAKE'

    op_rebake = row_batch.operator("object.gn_bake_batch", text="Rebake", icon='FILE_REFRESH')
    op_rebake.mode = 'REBAKE'

    op_clean = row_batch.operator("object.gn_bake_batch", text="Clean", icon='TRASH')
    op_clean.mode = 'CLEAN'

    # 2. Selection & Filter Toolbar
    row_tools = layout.row(align=True)
    row_sel = row_tools.row(align=True)
    op_all = row_sel.operator("object.gn_bake_select_all", text="All")
    op_all.action = 'ALL'
    op_none = row_sel.operator("object.gn_bake_select_all", text="None")
    op_none.action = 'NONE'
    op_inv = row_sel.operator("object.gn_bake_select_all", text="Invert")
    op_inv.action = 'INVERT'

    if state:
        row_tools.prop(state, "show_missing_only", text="", icon='HIDE_ON' if state.show_missing_only else 'HIDE_OFF')
        row_filter = layout.row(align=True)
        row_filter.prop(state, "filter_text", text="", icon='VIEWZOOM', placeholder="Filter bake nodes...")

    if not items:
        box_empty = layout.box()
        if filter_text or missing_only:
            box_empty.label(text="No bake nodes match current filters.", icon='FILTER')
        else:
            box_empty.label(text="No Geometry Nodes bake nodes on object.", icon='INFO')
        return

    # 3. Group by modifier
    items_by_mod = {}
    for item in items:
        mod_name = item["modifier_name"]
        if mod_name not in items_by_mod:
            items_by_mod[mod_name] = []
        items_by_mod[mod_name].append(item)

    layout.separator(factor=0.5)

    # 4. Clean & focused listing of bake nodes per modifier
    for mod_name, mod_items in items_by_mod.items():
        mod_box = layout.box()
        header_row = mod_box.row(align=True)
        header_row.label(text=f"{mod_name}", icon='NODETREE')
        header_row.label(text=f"({len(mod_items)} {'Bake' if len(mod_items) == 1 else 'Bakes'})")

        for item in mod_items:
            bake_item = item["bake_item"]
            setting = item.get("setting")
            node = item.get("node")
            has_cache = item.get("has_cache", False)

            row = mod_box.row(align=True)

            # 1. Selection checkbox
            if setting:
                row.prop(setting, "is_selected", text="")
            else:
                row.label(text="", icon='CHECKBOX_HLT')

            # 2. Jump to node button
            if item.get("node_tree") and node:
                op_jump = row.operator("object.gn_bake_jump_to_node", text="", icon='TARGET')
                op_jump.node_tree_name = item["node_tree"].name
                op_jump.node_name = node.name
            else:
                row.label(text="", icon='BLANK1')

            # 3. Bake Node Label / Group Path
            display_name = item.get("display_name", "Bake Node")
            row.label(text=display_name, icon='PINNED' if has_cache else 'UNPINNED')

            # 4. Mode badge (STILL / ANIMATION)
            mode_text = getattr(bake_item, "bake_mode", "STILL")
            row.label(text=mode_text)

            # 5. Status indicator
            stat_icon = 'CHECKMARK' if has_cache else 'RADIOBUT_OFF'
            row.label(text="", icon=stat_icon)


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
        draw_gn_bake_ui(self.layout, context, is_npanel=False)


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
        draw_gn_bake_ui(self.layout, context, is_npanel=True)


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
