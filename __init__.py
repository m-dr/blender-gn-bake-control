bl_info = {
    "name": "GN Bake Control",
    "author": "MD <m-dr>",
    "version": (0, 1, 0),
    "blender": (5, 2, 0),
    "location": "Properties > Modifiers & 3D View > Sidebar > GN Bake",
    "description": "Traverse, batch bake, and manage Geometry Nodes bake items in execution order",
    "category": "Node",
}

import importlib
import sys

if "bpy" in locals():
    # When Reload Scripts (F8 / bpy.ops.script.reload) is called:
    for mod in [preferences, properties, traversal, operators, ui]:
        if mod:
            importlib.reload(mod)

import bpy
from . import preferences
from . import properties
from . import traversal
from . import operators
from . import ui

modules = (
    preferences,
    properties,
    operators,
    ui,
)


class OBJECT_OT_gn_bake_reload_addon(bpy.types.Operator):
    bl_idname = "object.gn_bake_reload_addon"
    bl_label = "Reload GN Bake Control"
    bl_description = "Live reload all GN Bake Control python modules from disk without restarting Blender"
    bl_options = {'REGISTER'}

    def execute(self, context):
        for mod in reversed(modules):
            try:
                mod.unregister()
            except Exception as e:
                print(f"[GN Bake Control] Unregister warning: {e}")

        # Reload modules in order
        for mod in [preferences, properties, traversal, operators, ui]:
            try:
                importlib.reload(mod)
            except Exception as e:
                print(f"[GN Bake Control] Reload error in {mod.__name__}: {e}")

        for mod in modules:
            try:
                mod.register()
            except Exception as e:
                print(f"[GN Bake Control] Register error in {mod.__name__}: {e}")

        self.report({'INFO'}, "GN Bake Control (DEV) reloaded from disk!")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(OBJECT_OT_gn_bake_reload_addon)
    for mod in modules:
        mod.register()


def unregister():
    for mod in reversed(modules):
        mod.unregister()
    bpy.utils.unregister_class(OBJECT_OT_gn_bake_reload_addon)


if __name__ == "__main__":
    register()
