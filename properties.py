import bpy
from bpy.types import PropertyGroup, Operator
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


def find_bake_setting(obj, modifier_name, bake_id):
    """Read-only lookup for setting PropertyGroup. Safe to call inside UI draw()."""
    if not obj or not hasattr(obj, "gn_bake_state"):
        return None
    state = obj.gn_bake_state
    for item in state.items:
        if item.bake_id == bake_id and item.modifier_name == modifier_name:
            return item
    return None


def ensure_bake_setting(obj, modifier_name, bake_id, node_name=""):
    """Lookup or initialize settings PropertyGroup. MUST only be called outside UI draw (operators/handlers)."""
    if not obj or not hasattr(obj, "gn_bake_state"):
        return None
    state = obj.gn_bake_state

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


def is_bake_selected(obj, modifier_name, bake_id):
    """Check if item is selected (defaults to True if not yet in state)."""
    setting = find_bake_setting(obj, modifier_name, bake_id)
    if setting is not None:
        return setting.is_selected
    return True


class OBJECT_OT_gn_bake_toggle_item(Operator):
    bl_idname = "object.gn_bake_toggle_item"
    bl_label = "Toggle Selection"
    bl_description = "Toggle inclusion of this bake node in batch operations"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_name: StringProperty(name="Modifier Name", default="")
    bake_id: IntProperty(name="Bake ID", default=0)

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}

        setting = ensure_bake_setting(obj, self.modifier_name, self.bake_id)
        if setting:
            setting.is_selected = not setting.is_selected

        return {'FINISHED'}


classes = (
    GNBakeNodeItemSetting,
    GNBakeObjectState,
    OBJECT_OT_gn_bake_toggle_item,
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
