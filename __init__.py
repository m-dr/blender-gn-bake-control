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
    # Reload submodules when VS Code or Blender triggers reload
    for mod in (preferences, properties, traversal, operators, ui):
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


def register():
    for mod in modules:
        mod.register()


def unregister():
    for mod in reversed(modules):
        mod.unregister()


if __name__ == "__main__":
    register()
