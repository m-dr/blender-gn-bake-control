import bpy
import json
import time
from bpy.types import PropertyGroup
from bpy.props import BoolProperty, StringProperty, PointerProperty, EnumProperty, IntProperty


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
    show_stats: BoolProperty(
        name="Show Stats",
        description="Show bake timing and performance statistics",
        default=False,
    )
    show_frame_range: BoolProperty(
        name="Show Frame Info",
        description="Show or hide frame numbers / range column",
        default=True,
    )
    static_bake_mode: EnumProperty(
        name="Static Bake Frame",
        description="Target frame policy when (re)baking static still bakes",
        items=[
            ('CURRENT', "Current Frame", "Bake at active scene timeline frame"),
            ('ORIGINAL', "Original Frame", "Bake at the frame the node was previously baked at"),
            ('GLOBAL', "Global Frame", "Bake at a user-defined global frame"),
        ],
        default='CURRENT',
    )
    static_global_frame: IntProperty(
        name="Global Static Frame",
        description="Global frame used for static bakes when in Global Frame mode",
        default=1,
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
    bake_durations_json: StringProperty(
        name="Bake Durations JSON",
        description="JSON dictionary storing last measured bake durations (seconds) per modifier and bake_id",
        default="{}",
    )
    bake_recorded_frames_json: StringProperty(
        name="Bake Recorded Frames JSON",
        description="JSON dictionary storing frame number at which static nodes were baked",
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

    def get_durations(self):
        try:
            return json.loads(self.bake_durations_json) if self.bake_durations_json else {}
        except Exception:
            return {}

    def get_bake_duration(self, mod_name, bake_id):
        durations = self.get_durations()
        return durations.get(f"{mod_name}::{bake_id}", 0.0)

    def set_bake_duration(self, mod_name, bake_id, duration_sec):
        durations = self.get_durations()
        key = f"{mod_name}::{bake_id}"
        durations[key] = round(float(duration_sec), 3)
        self.bake_durations_json = json.dumps(durations)

    def get_recorded_frames(self):
        try:
            return json.loads(self.bake_recorded_frames_json) if self.bake_recorded_frames_json else {}
        except Exception:
            return {}

    def get_recorded_frame(self, mod_name, bake_id):
        frames = self.get_recorded_frames()
        return frames.get(f"{mod_name}::{bake_id}")

    def set_recorded_frame(self, mod_name, bake_id, frame_num):
        frames = self.get_recorded_frames()
        key = f"{mod_name}::{bake_id}"
        frames[key] = int(frame_num)
        self.bake_recorded_frames_json = json.dumps(frames)


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
