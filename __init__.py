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


def register():
    # Reload submodules if reloaded in-place
    for mod in (preferences, properties, traversal, operators, ui):
        try:
            importlib.reload(mod)
        except Exception:
            pass

    for mod in modules:
        try:
            mod.register()
        except Exception as e:
            print(f"[GN Bake Control] Registration error in {mod.__name__}: {e}")


def unregister():
    for mod in reversed(modules):
        try:
            mod.unregister()
        except Exception:
            pass


if __name__ == "__main__":
    register()
