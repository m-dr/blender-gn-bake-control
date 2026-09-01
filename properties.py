import bpy
import json
import time
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
    bake_timestamps_json: StringProperty(
        name="Bake Timestamps JSON",
        description="JSON dictionary storing last bake timestamps per modifier and bake_id",
        default="{}",
    )

    def get_timestamps(self):
        try:
            return json.loads(self.bake_timestamps_json) if self.bake_timestamps_json else {}
        except Exception:
            return {}

    def set_bake_timestamp(self, mod_name, bake_id, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        ts = self.get_timestamps()
        key = f"{mod_name}::{bake_id}"
        ts[key] = timestamp
        self.bake_timestamps_json = json.dumps(ts)

    def clear_bake_timestamp(self, mod_name, bake_id):
        ts = self.get_timestamps()
        key = f"{mod_name}::{bake_id}"
        if key in ts:
            del ts[key]
            self.bake_timestamps_json = json.dumps(ts)


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
