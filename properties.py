import bpy
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, PointerProperty


class GNBakeObjectState(PropertyGroup):
    show_disconnected: BoolProperty(
        name="Show Disconnected",
        description="Show disconnected or unused bake nodes at the bottom of the list",
        default=True,
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
