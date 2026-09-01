import bpy
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, StringProperty, PointerProperty


class GNBakeObjectState(PropertyGroup):
    show_disconnected: BoolProperty(
        name="Show Disconnected & Muted",
        description="Show disconnected or muted bake nodes in the list",
        default=True,
    )
    flatten_hierarchy: BoolProperty(
        name="Flatten Hierarchy",
        description="Hide group headers and display all bakes in a flat list without indentation",
        default=False,
    )
    collapsed_groups: StringProperty(
        name="Collapsed Groups",
        description="Semicolon-separated list of collapsed group keys",
        default="",
    )


classes = (
    GNBakeObjectState,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass
    bpy.types.Object.gn_bake_state = PointerProperty(type=GNBakeObjectState)


def unregister():
    if hasattr(bpy.types.Object, "gn_bake_state"):
        del bpy.types.Object.gn_bake_state
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
