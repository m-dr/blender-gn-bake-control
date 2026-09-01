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
    for item in obj.gn_bake_state.items:
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


def ensure_object_bake_settings(obj):
    """Synchronize state.items with all current bake items on the object."""
    if not obj or not hasattr(obj, "modifiers") or not hasattr(obj, "gn_bake_state"):
        return
    state = obj.gn_bake_state

    existing_keys = set()
    for mod in obj.modifiers:
        if mod.type == 'NODES' and hasattr(mod, "bakes"):
            for b in mod.bakes:
                existing_keys.add((mod.name, b.bake_id))
                found = False
                for item in state.items:
                    if item.modifier_name == mod.name and item.bake_id == b.bake_id:
                        found = True
                        break
                if not found:
                    item = state.items.add()
                    item.modifier_name = mod.name
                    item.bake_id = b.bake_id
                    item.node_name = b.node.name if getattr(b, "node", None) else ""
                    item.is_selected = True
                    item.custom_still_frame = bpy.context.scene.frame_current if (hasattr(bpy, "context") and bpy.context and bpy.context.scene) else 1

    # Remove stale items
    stale_indices = [i for i, item in enumerate(state.items) if (item.modifier_name, item.bake_id) not in existing_keys]
    for i in reversed(stale_indices):
        state.items.remove(i)


def is_bake_selected(obj, modifier_name, bake_id):
    """Check if item is selected (defaults to True if not yet in state)."""
    setting = find_bake_setting(obj, modifier_name, bake_id)
    if setting is not None:
        return setting.is_selected
    return True


@bpy.app.handlers.persistent
def sync_bake_settings_handler(scene, depsgraph):
    for update in depsgraph.updates:
        if isinstance(update.id, bpy.types.Object):
            ensure_object_bake_settings(update.id)


@bpy.app.handlers.persistent
def on_file_load_handler(dummy):
    for obj in bpy.data.objects:
        ensure_object_bake_settings(obj)


classes = (
    GNBakeNodeItemSetting,
    GNBakeObjectState,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.gn_bake_state = PointerProperty(type=GNBakeObjectState)

    if sync_bake_settings_handler not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(sync_bake_settings_handler)
    if on_file_load_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(on_file_load_handler)


def unregister():
    if sync_bake_settings_handler in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(sync_bake_settings_handler)
    if on_file_load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(on_file_load_handler)

    if hasattr(bpy.types.Object, "gn_bake_state"):
        del bpy.types.Object.gn_bake_state
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
