import bpy
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, IntProperty, StringProperty, CollectionProperty, PointerProperty


class GNBakeNodeItemSetting(PropertyGroup):
    bake_id: IntProperty(
        name="Bake ID",
        description="Internal Blender bake ID matching NodesModifierBake",
        default=0,
    )
    modifier_name: StringProperty(
        name="Modifier Name",
        description="Modifier owning this bake node",
        default="",
    )
    node_name: StringProperty(
        name="Node Name",
        description="Bake node name in node tree",
        default="",
    )
    is_selected: BoolProperty(
        name="Selected",
        description="Include this bake node in batch operations",
        default=True,
    )
    custom_still_frame: IntProperty(
        name="Still Frame",
        description="Frame number to evaluate and bake when mode is STILL",
        default=1,
    )
    use_custom_still_frame: BoolProperty(
        name="Custom Still Frame",
        description="Use specified frame for still baking instead of current scene frame",
        default=False,
    )
    is_expanded: BoolProperty(
        name="Expand",
        description="Expand additional parameters for this bake node",
        default=False,
    )


class GNBakeObjectState(PropertyGroup):
    items: CollectionProperty(type=GNBakeNodeItemSetting)
    filter_text: StringProperty(
        name="Filter",
        description="Filter bake nodes by name or modifier",
        default="",
    )
    compact_ui: BoolProperty(
        name="Compact UI",
        description="Render compact rows to save vertical screen space",
        default=True,
    )
    show_missing_only: BoolProperty(
        name="Missing Only",
        description="Show only unbaked / missing nodes",
        default=False,
    )


def get_or_create_bake_setting(obj, modifier_name, bake_id, node_name=""):
    """Lookup or initialize settings PropertyGroup for a specific bake item on an object."""
    state = getattr(obj, "gn_bake_state", None)
    if not state:
        return None

    # Search existing
    for item in state.items:
        if item.bake_id == bake_id and item.modifier_name == modifier_name:
            return item

    # Create new
    item = state.items.add()
    item.bake_id = bake_id
    item.modifier_name = modifier_name
    item.node_name = node_name
    item.is_selected = True
    item.custom_still_frame = bpy.context.scene.frame_current if bpy.context.scene else 1
    return item


classes = (
    GNBakeNodeItemSetting,
    GNBakeObjectState,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.gn_bake_state = PointerProperty(type=GNBakeObjectState)


def unregister():
    if hasattr(bpy.types.Object, "gn_bake_state"):
        del bpy.types.Object.gn_bake_state
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
