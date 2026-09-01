import bpy
from bpy.types import AddonPreferences
from bpy.props import BoolProperty, StringProperty

class GNBakeControlPreferences(AddonPreferences):
    bl_idname = __package__ if __package__ else "gn_bake_control"

    show_in_modifier_stack: BoolProperty(
        name="Show in Modifier Properties",
        description="Display the GN Bake Control panel at the top of the Modifier Stack in Properties",
        default=True,
    )

    show_in_3dview_sidebar: BoolProperty(
        name="Show in 3D View Sidebar (N-Panel)",
        description="Display the GN Bake Control panel in the 3D Viewport sidebar tab",
        default=True,
    )

    category: StringProperty(
        name="Sidebar Tab Name",
        description="Category tab name for the 3D Viewport sidebar panel",
        default="GN Bake (DEV)",
    )

    auto_restore_frame: BoolProperty(
        name="Restore Frame After Still Bake",
        description="Restore original scene frame after baking still bakes with custom frame numbers",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="Panel Locations:", icon='PREFERENCES')
        box.prop(self, "show_in_modifier_stack")
        row = box.row(align=True)
        row.prop(self, "show_in_3dview_sidebar")
        if self.show_in_3dview_sidebar:
            row.prop(self, "category", text="Tab Name")

        box2 = layout.box()
        box2.label(text="Bake Behavior:", icon='PHYSICS')
        box2.prop(self, "auto_restore_frame")


def get_preferences(context=None):
    if context is None:
        context = bpy.context

    pkg = __package__ if __package__ else ""
    candidates = [
        pkg,
        "bl_ext.vscode_development.gn_bake_control",
        "bl_ext.user_default.gn_bake_control",
        "gn_bake_control",
    ]
    if pkg and "." in pkg:
        # e.g. bl_ext.vscode_development.gn_bake_control
        parts = pkg.split(".")
        if len(parts) >= 3:
            candidates.insert(0, ".".join(parts[:3]))

    for name in candidates:
        if name and name in context.preferences.addons:
            addon = context.preferences.addons[name]
            if addon and addon.preferences:
                return addon.preferences
    return None


classes = (
    GNBakeControlPreferences,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
