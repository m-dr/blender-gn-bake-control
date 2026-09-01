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
    compact_ui = state.compact_ui if state else True

    items = get_object_bake_items(obj, filter_text=filter_text, missing_only=missing_only)

    # 1. Global Batch Actions Toolbar
    col_top = layout.column(align=True)
    row_batch = col_top.row(align=True)
    row_batch.scale_y = 1.25

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
        row_tools.prop(state, "compact_ui", text="", icon='COLLAPSEMENU' if state.compact_ui else 'MENU_PANEL')
        row_tools.prop(state, "show_missing_only", text="", icon='HIDE_ON' if state.show_missing_only else 'HIDE_OFF')

    if state:
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

    # 4. Draw items per modifier
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

            if compact_ui:
                # Compact Row
                item_row = mod_box.row(align=True)

                # Selection checkbox
                if setting:
                    item_row.prop(setting, "is_selected", text="")
                else:
                    item_row.label(text="", icon='CHECKBOX_HLT')

                # Jump to node button
                if item["node_tree"] and node:
                    op_jump = item_row.operator("object.gn_bake_jump_to_node", text="", icon='TARGET')
                    op_jump.node_tree_name = item["node_tree"].name
                    op_jump.node_name = node.name

                # Node Label / Path
                display_label = item["display_name"]
                if len(display_label) > 18:
                    display_label = display_label[:16] + ".."
                item_row.label(text=display_label)

                # Mode selector
                item_row.prop(bake_item, "bake_mode", text="")

                # Frame settings inline
                if bake_item.bake_mode == 'STILL':
                    if setting:
                        item_row.prop(setting, "use_custom_still_frame", text="", icon='TIME')
                        if setting.use_custom_still_frame:
                            item_row.prop(setting, "custom_still_frame", text="")
                        else:
                            sub = item_row.row(align=True)
                            sub.enabled = False
                            sub.label(text=f"F:{context.scene.frame_current}")
                    else:
                        sub = item_row.row(align=True)
                        sub.enabled = False
                        sub.label(text=f"F:{context.scene.frame_current}")
                else: # ANIMATION
                    item_row.prop(bake_item, "use_custom_simulation_frame_range", text="", icon='TIME')
                    if bake_item.use_custom_simulation_frame_range:
                        item_row.prop(bake_item, "frame_start", text="")
                        item_row.prop(bake_item, "frame_end", text="")
                    else:
                        sub = item_row.row(align=True)
                        sub.enabled = False
                        sub.label(text=f"{context.scene.frame_start}..{context.scene.frame_end}")

                # Status indicator
                stat_icon = 'CHECKMARK' if has_cache else 'RADIOBUT_OFF'
                item_row.label(text="", icon=stat_icon)

                # Action buttons
                op_single_bake = item_row.operator("object.gn_bake_single_action", text="", icon='PHYSICS')
                op_single_bake.action = 'BAKE'
                op_single_bake.modifier_name = mod_name
                op_single_bake.bake_id = bake_item.bake_id

                op_single_clean = item_row.operator("object.gn_bake_single_action", text="", icon='X')
                op_single_clean.action = 'CLEAN'
                op_single_clean.modifier_name = mod_name
                op_single_clean.bake_id = bake_item.bake_id

            else:
                # Detailed Card View
                card = mod_box.box()
                top_r = card.row(align=True)

                if setting:
                    top_r.prop(setting, "is_selected", text="")
                else:
                    top_r.label(text="", icon='CHECKBOX_HLT')

                if item["node_tree"] and node:
                    op_jump = top_r.operator("object.gn_bake_jump_to_node", text="", icon='TARGET')
                    op_jump.node_tree_name = item["node_tree"].name
                    op_jump.node_name = node.name

                top_r.label(text=item["display_name"], icon='PINNED' if has_cache else 'UNPINNED')

                # Right side action buttons
                op_sb = top_r.operator("object.gn_bake_single_action", text="Bake", icon='PHYSICS')
                op_sb.action = 'BAKE'
                op_sb.modifier_name = mod_name
                op_sb.bake_id = bake_item.bake_id

                op_sc = top_r.operator("object.gn_bake_single_action", text="Clean", icon='X')
                op_sc.action = 'CLEAN'
                op_sc.modifier_name = mod_name
                op_sc.bake_id = bake_item.bake_id

                # Controls row
                ctrl_row = card.row(align=True)
                ctrl_row.prop(bake_item, "bake_mode", text="Mode")

                if bake_item.bake_mode == 'STILL':
                    if setting:
                        ctrl_row.prop(setting, "use_custom_still_frame", text="Custom Frame")
                        if setting.use_custom_still_frame:
                            ctrl_row.prop(setting, "custom_still_frame", text="Frame")
                else:
                    ctrl_row.prop(bake_item, "use_custom_simulation_frame_range", text="Custom Range")
                    if bake_item.use_custom_simulation_frame_range:
                        range_row = card.row(align=True)
                        range_row.prop(bake_item, "frame_start", text="Start")
                        range_row.prop(bake_item, "frame_end", text="End")


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
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
