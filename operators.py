import bpy
from bpy.types import Operator
from bpy.props import EnumProperty, BoolProperty, StringProperty, IntProperty
from contextlib import contextmanager

from .traversal import get_object_bake_items
from .preferences import get_preferences


def status_text_set(context, text):
    """Set workspace status text safely across Blender versions."""
    workspace = getattr(context, "workspace", None)
    if workspace and hasattr(workspace, "status_text_set"):
        workspace.status_text_set(text)
        return
    wm = getattr(context, "window_manager", None)
    if wm and hasattr(wm, "status_text_set"):
        wm.status_text_set(text)


@contextmanager
def active_object_ctx(ctx, obj):
    """Context manager to ensure the target object is active and selected."""
    view_layer = ctx.view_layer
    prev_active = view_layer.objects.active
    prev_selected = list(ctx.selected_objects)
    try:
        for s in prev_selected:
            s.select_set(False)
        obj.select_set(True)
        view_layer.objects.active = obj
        yield
    finally:
        for s in prev_selected:
            if s and s.name in ctx.scene.objects:
                s.select_set(True)
        if prev_active and prev_active.name in ctx.scene.objects:
            view_layer.objects.active = prev_active


class OBJECT_OT_gn_bake_batch(Operator):
    bl_idname = "object.gn_bake_batch"
    bl_label = "GN Batch Bake"
    bl_description = "Execute batch bake, rebake, or clean operations on Geometry Nodes bake items"
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(
        name="Mode",
        items=[
            ('BAKE', "Bake", "Bake selected items"),
            ('REBAKE', "Rebake", "Clean cache and rebake selected items"),
            ('CLEAN', "Clean", "Clean / delete cache for selected items"),
        ],
        default='BAKE',
    )

    selected_only: BoolProperty(
        name="Selected Only",
        description="Process only checked bake items",
        default=True,
    )

    _timer = None
    _jobs = []
    _total = 0
    _done = 0
    _orig_frame = 1
    _had_frame_change = False

    def invoke(self, context, event):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object selected.")
            return {'CANCELLED'}

        raw_items = get_object_bake_items(obj)
        if not raw_items:
            self.report({'INFO'}, "No Geometry Nodes bake nodes found on active object.")
            return {'CANCELLED'}

        # Filter jobs
        jobs = []
        for item in raw_items:
            setting = item.get("setting")
            if self.selected_only and setting and not setting.is_selected:
                continue
            jobs.append(item)

        if not jobs:
            self.report({'INFO'}, "No bake nodes selected for batch operation.")
            return {'CANCELLED'}

        self._jobs = jobs
        self._total = len(jobs)
        self._done = 0
        self._orig_frame = context.scene.frame_current
        self._had_frame_change = False

        wm = context.window_manager
        wm.progress_begin(0, self._total)
        status_text_set(context, f"GN Bake [{self.mode}]: 0/{self._total}")

        self._timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager

        if event.type == 'ESC':
            self._finish(context, cancelled=True)
            self.report({'WARNING'}, f"GN Bake [{self.mode}] cancelled by user.")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            if self._jobs:
                job = self._jobs.pop(0)
                self._execute_single_job(context, job)
                self._done += 1
                wm.progress_update(self._done)
                status_text_set(context, f"GN Bake [{self.mode}]: {self._done}/{self._total} ({job['display_name']})")
            else:
                self._finish(context)
                self.report({'INFO'}, f"GN Bake [{self.mode}] completed ({self._total} items processed).")
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def _execute_single_job(self, context, job):
        obj = job["object"]
        mod = job["modifier"]
        bake_id = job["bake_id"]
        setting = job.get("setting")
        bake_item = job["bake_item"]

        with active_object_ctx(context, obj):
            uid = obj.session_uid

            if self.mode == 'CLEAN':
                try:
                    bpy.ops.object.geometry_node_bake_delete_single(
                        session_uid=uid,
                        modifier_name=mod.name,
                        bake_id=bake_id,
                    )
                except Exception as e:
                    self.report({'ERROR'}, f"Clean failed for {job['display_name']}: {e}")

            elif self.mode == 'REBAKE':
                try:
                    bpy.ops.object.geometry_node_bake_delete_single(
                        session_uid=uid,
                        modifier_name=mod.name,
                        bake_id=bake_id,
                    )
                except Exception:
                    pass

                self._bake_node_item(context, uid, mod.name, bake_id, bake_item, setting)

            elif self.mode == 'BAKE':
                self._bake_node_item(context, uid, mod.name, bake_id, bake_item, setting)

    def _bake_node_item(self, context, session_uid, mod_name, bake_id, bake_item, setting):
        # Still mode custom frame handling
        if bake_item.bake_mode == 'STILL' and setting and setting.use_custom_still_frame:
            target_frame = setting.custom_still_frame
            if context.scene.frame_current != target_frame:
                context.scene.frame_set(target_frame)
                self._had_frame_change = True

        try:
            bpy.ops.object.geometry_node_bake_single(
                session_uid=session_uid,
                modifier_name=mod_name,
                bake_id=bake_id,
            )
        except Exception as e:
            self.report({'ERROR'}, f"Bake failed for modifier '{mod_name}' (ID {bake_id}): {e}")

    def _finish(self, context, cancelled=False):
        wm = context.window_manager
        if self._timer:
            wm.event_timer_remove(self._timer)
            self._timer = None

        wm.progress_end()
        status_text_set(context, None)

        prefs = get_preferences(context)
        restore = prefs.auto_restore_frame if prefs else True
        if restore and self._had_frame_change:
            context.scene.frame_set(self._orig_frame)


class OBJECT_OT_gn_bake_single_action(Operator):
    bl_idname = "object.gn_bake_single_action"
    bl_label = "Bake Action"
    bl_description = "Execute bake, rebake, or clean on this single bake node"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=[
            ('BAKE', "Bake", "Bake this node"),
            ('REBAKE', "Rebake", "Delete cache and rebake this node"),
            ('CLEAN', "Clean", "Clean / delete cache for this node"),
        ],
        default='BAKE',
    )
    modifier_name: StringProperty(name="Modifier Name", default="")
    bake_id: IntProperty(name="Bake ID", default=0)

    def execute(self, context):
        obj = context.active_object
        if not obj or not self.modifier_name:
            return {'CANCELLED'}

        mod = obj.modifiers.get(self.modifier_name)
        if not mod or not hasattr(mod, "bakes"):
            return {'CANCELLED'}

        bake_item = None
        for b in mod.bakes:
            if b.bake_id == self.bake_id:
                bake_item = b
                break

        if not bake_item:
            self.report({'WARNING'}, f"Bake ID {self.bake_id} not found on modifier '{self.modifier_name}'")
            return {'CANCELLED'}

        uid = obj.session_uid
        orig_frame = context.scene.frame_current

        if self.action in {'CLEAN', 'REBAKE'}:
            try:
                bpy.ops.object.geometry_node_bake_delete_single(
                    session_uid=uid,
                    modifier_name=mod.name,
                    bake_id=self.bake_id,
                )
            except Exception as e:
                if self.action == 'CLEAN':
                    self.report({'ERROR'}, f"Clean failed: {e}")
                    return {'CANCELLED'}

        if self.action in {'BAKE', 'REBAKE'}:
            # Check for custom still frame setting
            setting = None
            if hasattr(obj, "gn_bake_state"):
                for s in obj.gn_bake_state.items:
                    if s.bake_id == self.bake_id and s.modifier_name == self.modifier_name:
                        setting = s
                        break

            had_frame_change = False
            if bake_item.bake_mode == 'STILL' and setting and setting.use_custom_still_frame:
                if context.scene.frame_current != setting.custom_still_frame:
                    context.scene.frame_set(setting.custom_still_frame)
                    had_frame_change = True

            try:
                bpy.ops.object.geometry_node_bake_single(
                    session_uid=uid,
                    modifier_name=mod.name,
                    bake_id=self.bake_id,
                )
                self.report({'INFO'}, f"Bake finished for '{mod.name}' (ID {self.bake_id})")
            except Exception as e:
                self.report({'ERROR'}, f"Bake failed: {e}")
                return {'CANCELLED'}
            finally:
                prefs = get_preferences(context)
                if prefs and prefs.auto_restore_frame and had_frame_change:
                    context.scene.frame_set(orig_frame)

        return {'FINISHED'}


class OBJECT_OT_gn_bake_select_all(Operator):
    bl_idname = "object.gn_bake_select_all"
    bl_label = "Select All / None"
    bl_description = "Select, deselect, or invert selection of bake nodes on the active object"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=[
            ('ALL', "All", "Select all bake nodes"),
            ('NONE', "None", "Deselect all bake nodes"),
            ('INVERT', "Invert", "Invert bake node selection"),
        ],
        default='ALL',
    )

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}

        items = get_object_bake_items(obj)
        for item in items:
            setting = item.get("setting")
            if setting:
                if self.action == 'ALL':
                    setting.is_selected = True
                elif self.action == 'NONE':
                    setting.is_selected = False
                elif self.action == 'INVERT':
                    setting.is_selected = not setting.is_selected

        return {'FINISHED'}


class OBJECT_OT_gn_bake_jump_to_node(Operator):
    bl_idname = "object.gn_bake_jump_to_node"
    bl_label = "Jump to Bake Node"
    bl_description = "Focus and center on this bake node in the Geometry Node Editor"
    bl_options = {'REGISTER', 'UNDO'}

    node_tree_name: StringProperty(name="Node Tree Name", default="")
    node_name: StringProperty(name="Node Name", default="")

    def execute(self, context):
        if not self.node_tree_name or not self.node_name:
            return {'CANCELLED'}

        ntree = bpy.data.node_groups.get(self.node_tree_name)
        if not ntree:
            self.report({'WARNING'}, f"Node tree '{self.node_tree_name}' not found.")
            return {'CANCELLED'}

        target_node = ntree.nodes.get(self.node_name)
        if not target_node:
            self.report({'WARNING'}, f"Node '{self.node_name}' not found in '{self.node_tree_name}'.")
            return {'CANCELLED'}

        # Find any visible Node Editor area
        node_space = None
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        node_space = space
                        break
                if node_space:
                    break

        if node_space:
            node_space.tree_type = 'GeometryNodeTree'
            node_space.node_tree = ntree

        # Deselect all and select target
        for n in ntree.nodes:
            n.select = False
        target_node.select = True
        ntree.nodes.active = target_node

        self.report({'INFO'}, f"Selected '{target_node.name}' in '{ntree.name}'")
        return {'FINISHED'}


classes = (
    OBJECT_OT_gn_bake_batch,
    OBJECT_OT_gn_bake_single_action,
    OBJECT_OT_gn_bake_select_all,
    OBJECT_OT_gn_bake_jump_to_node,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
