import bpy
from bpy.types import Panel

from .traversal import get_object_bake_list
from .preferences import get_preferences


def draw_gn_bake_ui(layout, context):
    obj = context.active_object
    if not obj:
        layout.label(text="Select an object to inspect bakes", icon='INFO')
        return

    mod_data = get_object_bake_list(obj, scene=context.scene)

    if not mod_data:
        box = layout.box()
        box.label(text="No active Geometry Nodes bake nodes on object.", icon='INFO')
        return

    for entry in mod_data:
        mod_name = entry["modifier_name"]
        bakes = entry["bakes"]

        box = layout.box()
        # Modifier header
        head = box.row(align=True)
        head.label(text=f"{mod_name}", icon='NODETREE')
        head.label(text=f"({len(bakes)} {'Active Bake' if len(bakes) == 1 else 'Active Bakes'})")

        # List each bake node with details
        for b in bakes:
            row = box.row(align=True)
            # Status icon
            icon = 'CHECKMARK' if b["has_cache"] else 'RADIOBUT_OFF'
            row.label(text="", icon=icon)

            # Node display name / path
            row.label(text=b["path"], icon='PHYSICS')

            # Mode badge
            row.label(text=f"[{b['mode']}]")

            # Frame range / still frame info
            row.label(text=b["frame_info"], icon='TIME')


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
