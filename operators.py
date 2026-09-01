import bpy
import time
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty, EnumProperty


# Global runtime tracking for active batch baking visual states
ACTIVE_BATCH_STATE = {
    "is_baking": False,
    "object_name": "",
    "status": {},  # bake_id: 'PENDING' | 'CURRENT' | 'DONE'
}


def find_group_chain(current_tree, target_tree, visited=None):
    """
    Recursively find the sequence of (sub_tree, group_node) leading from current_tree to target_tree.
    """
    if not current_tree or not target_tree:
        return None
    if current_tree == target_tree:
        return []
    if visited is None:
        visited = set()
    if current_tree in visited:
        return None
    visited = visited | {current_tree}

    for node in current_tree.nodes:
        if node.type == 'GROUP' and getattr(node, "node_tree", None):
            if node.node_tree == target_tree:
                return [(node.node_tree, node)]
            sub_chain = find_group_chain(node.node_tree, target_tree, visited=visited)
            if sub_chain is not None:
                return [(node.node_tree, node)] + sub_chain
    return None


class OBJECT_OT_gn_bake_navigate_to(Operator):
    # TODO: Fix node editor navigation/framing across nested spaces (marked as pending/broken for future rework)
    bl_idname = "object.gn_bake_navigate_to"
    bl_label = "Navigate to Node"
    bl_description = "Focus, navigate to, and frame this modifier or bake node in the Geometry Node Editor"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_name: StringProperty(name="Modifier Name", default="")
    node_tree_name: StringProperty(name="Node Tree Name", default="")
    node_name: StringProperty(name="Node Name", default="")
    group_chain_json: StringProperty(name="Group Chain JSON", default="[]")

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}

        # 1. If modifier is specified, set active in modifier stack
        root_tree = None
        if self.modifier_name:
            mod = obj.modifiers.get(self.modifier_name)
            if mod:
                try:
                    obj.modifiers.active = mod
                except Exception:
                    pass
                if mod.type == 'NODES':
                    root_tree = mod.node_group

        # 2. Find target node tree
        ntree = None
        if self.node_tree_name:
            ntree = bpy.data.node_groups.get(self.node_tree_name)
        elif root_tree:
            ntree = root_tree

        if not root_tree and ntree:
            root_tree = ntree

        if not root_tree and not ntree:
            self.report({'WARNING'}, "No node tree found to navigate to.")
            return {'CANCELLED'}

        target_tree = ntree if ntree else root_tree

        # 3. Find and update all Node Editor spaces in active screen
        found_node_editor = False

        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                found_node_editor = True
                space = area.spaces.active
                if not space:
                    continue

                region_win = None
                for r in area.regions:
                    if r.type == 'WINDOW':
                        region_win = r
                        break

                # Unpin and point Node Editor directly to the target node tree
                space.tree_type = 'GeometryNodeTree'
                space.pin = False
                space.node_tree = target_tree

                if self.node_name and target_tree:
                    target_node = target_tree.nodes.get(self.node_name)
                    if target_node:
                        for n in target_tree.nodes:
                            n.select = False
                        target_node.select = True
                        target_tree.nodes.active = target_node

                        area.tag_redraw()

                        # Focus view (Numpad .) onto the selected node
                        if not bpy.app.background and region_win:
                            try:
                                with context.temp_override(
                                    window=context.window,
                                    screen=context.screen,
                                    area=area,
                                    region=region_win,
                                    space_data=space
                                ):
                                    bpy.ops.node.view_selected()
                            except Exception:
                                pass

                        self.report({'INFO'}, f"Framed '{target_node.name}' in '{target_tree.name}'")
                        return {'FINISHED'}

                area.tag_redraw()

                # Frame all in node tree if navigating to modifier or whole tree
                if not bpy.app.background and region_win:
                    try:
                        with context.temp_override(
                            window=context.window,
                            screen=context.screen,
                            area=area,
                            region=region_win,
                            space_data=space
                        ):
                            bpy.ops.node.view_all()
                    except Exception:
                        pass

                self.report({'INFO'}, f"Navigated to '{target_tree.name}'")
                return {'FINISHED'}

        if not found_node_editor:
            self.report({'WARNING'}, "No Geometry Node Editor is open on screen.")
            return {'CANCELLED'}

        return {'FINISHED'}


class OBJECT_OT_gn_bake_single_action(Operator):
    bl_idname = "object.gn_bake_single_action"
    bl_label = "GN Bake Single Action"
    bl_description = "Bake or clear cache for a single Geometry Nodes bake node"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=[
            ('BAKE', "Bake", "Bake this node"),
            ('CLEAR', "Clear", "Clear cache for this node"),
        ],
        default='BAKE'
    )
    modifier_name: StringProperty(name="Modifier Name", default="")
    bake_id: IntProperty(name="Bake ID", default=0)

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object selected.")
            return {'CANCELLED'}

        if not self.modifier_name or not self.bake_id:
            self.report({'ERROR'}, "Invalid modifier or bake ID.")
            return {'CANCELLED'}

        mod = obj.modifiers.get(self.modifier_name)
        if not mod or mod.type != 'NODES':
            self.report({'ERROR'}, f"Modifier '{self.modifier_name}' not found.")
            return {'CANCELLED'}

        state = getattr(obj, "gn_bake_state", None)

        try:
            if self.action == 'BAKE':
                b_item = None
                for b in getattr(mod, "bakes", []):
                    if b.bake_id == self.bake_id:
                        b_item = b
                        break

                is_still = not (b_item and getattr(b_item, "bake_mode", "") == 'ANIMATION')
                orig_frame = context.scene.frame_current
                target_frame = orig_frame

                if is_still and state:
                    if state.static_bake_mode == 'ORIGINAL':
                        rec = state.get_recorded_frame(self.modifier_name, self.bake_id)
                        if rec is not None:
                            target_frame = rec
                    elif state.static_bake_mode == 'GLOBAL':
                        target_frame = state.static_global_frame

                try:
                    if is_still and context.scene.frame_current != target_frame:
                        context.scene.frame_set(target_frame)

                    t0 = time.time()
                    try:
                        if not bpy.app.background:
                            bpy.ops.object.geometry_node_bake_single(
                                'INVOKE_DEFAULT',
                                session_uid=obj.session_uid,
                                modifier_name=self.modifier_name,
                                bake_id=self.bake_id
                            )
                        else:
                            bpy.ops.object.geometry_node_bake_single(
                                session_uid=obj.session_uid,
                                modifier_name=self.modifier_name,
                                bake_id=self.bake_id
                            )
                    except Exception:
                        bpy.ops.object.geometry_node_bake_single(
                            session_uid=obj.session_uid,
                            modifier_name=self.modifier_name,
                            bake_id=self.bake_id
                        )

                    duration = time.time() - t0
                    if state:
                        state.set_bake_timestamp(self.modifier_name, self.bake_id)
                        state.set_bake_duration(self.modifier_name, self.bake_id, duration)
                        if is_still:
                            state.set_recorded_frame(self.modifier_name, self.bake_id, target_frame)

                    self.report({'INFO'}, f"Baked node (ID {self.bake_id}) in {self.modifier_name} ({duration:.1f}s)")
                finally:
                    if is_still and context.scene.frame_current != orig_frame:
                        context.scene.frame_set(orig_frame)

            elif self.action == 'CLEAR':
                bpy.ops.object.geometry_node_bake_delete_single(
                    session_uid=obj.session_uid,
                    modifier_name=self.modifier_name,
                    bake_id=self.bake_id
                )
                if state:
                    state.clear_bake_timestamp(self.modifier_name, self.bake_id)
                self.report({'INFO'}, f"Cleared cache for node (ID {self.bake_id}) in {self.modifier_name}")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, f"Bake action failed: {e}")
            return {'CANCELLED'}


class OBJECT_OT_gn_bake_batch_action(Operator):
    bl_idname = "object.gn_bake_batch_action"
    bl_label = "GN Bake Batch Action"
    bl_description = "Execute batch bake or clear operations across bake nodes in topological dependency order (Press ESC to cancel)"
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(
        name="Action",
        items=[
            ('REBAKE_STALE', "Rebake Stale", "Re-bake all stale bake nodes in topological dependency order"),
            ('CLEAR_STALE', "Clear Stale", "Clear cache for all stale bake nodes"),
            ('BAKE_ALL', "Bake All", "Bake all active connected nodes in topological dependency order"),
            ('CLEAR_ALL', "Clear All", "Clear cache for all bake nodes on this object"),
        ],
        default='REBAKE_STALE'
    )

    _timer = None
    _queue = []
    _current_idx = 0
    _orig_frame = 1
    _object_name = ""
    _total_duration = 0.0
    _baked_count = 0

    def invoke(self, context, event):
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object selected.")
            return {'CANCELLED'}

        # In background headless CLI tests, execute synchronously
        if bpy.app.background:
            return self.execute(context)

        from .traversal import get_object_bake_list
        mod_data = get_object_bake_list(obj, scene=context.scene, show_disconnected=True)
        if not mod_data:
            self.report({'INFO'}, "No Geometry Nodes bakes found on active object.")
            return {'CANCELLED'}

        if self.action in ('REBAKE_STALE', 'BAKE_ALL'):
            target_items = []
            for m in mod_data:
                m_name = m["modifier_name"]
                for b in m["bakes"]:
                    if not b.get("is_group") and b.get("is_connected") and not b.get("is_muted") and b.get("bake_id"):
                        if self.action == 'REBAKE_STALE' and b.get("cache_state") != 'STALE':
                            continue
                        target_items.append((m_name, b.get("bake_id"), b.get("name"), b.get("mode") == 'STILL'))

            if not target_items:
                msg = "No stale bake nodes found to rebake." if self.action == 'REBAKE_STALE' else "No active connected bake nodes found."
                self.report({'INFO'}, msg)
                return {'CANCELLED'}

            self._queue = target_items
            self._current_idx = 0
            self._object_name = obj.name
            self._orig_frame = context.scene.frame_current
            self._total_duration = 0.0
            self._baked_count = 0

            # Initialize global batch state for live UI color indicators
            ACTIVE_BATCH_STATE["is_baking"] = True
            ACTIVE_BATCH_STATE["object_name"] = obj.name
            ACTIVE_BATCH_STATE["status"] = {bake_id: 'PENDING' for (_, bake_id, _, _) in target_items}

            wm = context.window_manager
            self._timer = wm.event_timer_add(0.01, window=context.window)
            wm.modal_handler_add(self)
            self.report({'INFO'}, f"Batch baking {len(target_items)} node(s)... Press ESC to cancel.")
            return {'RUNNING_MODAL'}

        elif self.action in ('CLEAR_STALE', 'CLEAR_ALL'):
            return self.execute(context)

        return {'FINISHED'}

    def modal(self, context, event):
        # 1. Check for ESC key cancellation
        if event.type == 'ESC':
            self.cancel(context)
            self.report({'WARNING'}, "Batch baking cancelled by user.")
            return {'CANCELLED'}

        if event.type == 'TIMER':
            obj = bpy.data.objects.get(self._object_name)
            if not obj or self._current_idx >= len(self._queue):
                return self.finish(context)

            m_name, bake_id, b_name, is_still = self._queue[self._current_idx]
            state = getattr(obj, "gn_bake_state", None)

            # Mark current node active
            ACTIVE_BATCH_STATE["status"][bake_id] = 'CURRENT'
            for area in context.screen.areas:
                area.tag_redraw()

            target_frame = self._orig_frame
            if is_still and state:
                if state.static_bake_mode == 'ORIGINAL':
                    rec = state.get_recorded_frame(m_name, bake_id)
                    if rec is not None:
                        target_frame = rec
                elif state.static_bake_mode == 'GLOBAL':
                    target_frame = state.static_global_frame

            if is_still and context.scene.frame_current != target_frame:
                context.scene.frame_set(target_frame)

            t0 = time.time()
            try:
                try:
                    if not bpy.app.background:
                        bpy.ops.object.geometry_node_bake_single(
                            'INVOKE_DEFAULT',
                            session_uid=obj.session_uid,
                            modifier_name=m_name,
                            bake_id=bake_id
                        )
                    else:
                        bpy.ops.object.geometry_node_bake_single(
                            session_uid=obj.session_uid,
                            modifier_name=m_name,
                            bake_id=bake_id
                        )
                except Exception:
                    bpy.ops.object.geometry_node_bake_single(
                        session_uid=obj.session_uid,
                        modifier_name=m_name,
                        bake_id=bake_id
                    )

                dur = time.time() - t0
                self._total_duration += dur
                if state:
                    state.set_bake_timestamp(m_name, bake_id)
                    state.set_bake_duration(m_name, bake_id, dur)
                    if is_still:
                        state.set_recorded_frame(m_name, bake_id, target_frame)
                self._baked_count += 1
                ACTIVE_BATCH_STATE["status"][bake_id] = 'DONE'
            except Exception as e:
                self.report({'WARNING'}, f"Failed baking {b_name}: {e}")
                ACTIVE_BATCH_STATE["status"][bake_id] = 'DONE'

            self._current_idx += 1

            if self._current_idx >= len(self._queue):
                return self.finish(context)

        return {'RUNNING_MODAL'}

    def finish(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        ACTIVE_BATCH_STATE["is_baking"] = False
        ACTIVE_BATCH_STATE["status"] = {}

        if context.scene.frame_current != self._orig_frame:
            context.scene.frame_set(self._orig_frame)

        for area in context.screen.areas:
            area.tag_redraw()

        self.report({'INFO'}, f"Successfully baked {self._baked_count} node(s) in dependency order ({self._total_duration:.1f}s).")
        return {'FINISHED'}

    def cancel(self, context):
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        ACTIVE_BATCH_STATE["is_baking"] = False
        ACTIVE_BATCH_STATE["status"] = {}

        if context.scene.frame_current != self._orig_frame:
            context.scene.frame_set(self._orig_frame)

        for area in context.screen.areas:
            area.tag_redraw()

    def execute(self, context):
        # Synchronous fallback
        obj = context.active_object
        if not obj:
            self.report({'ERROR'}, "No active object selected.")
            return {'CANCELLED'}

        from .traversal import get_object_bake_list
        mod_data = get_object_bake_list(obj, scene=context.scene, show_disconnected=True)
        if not mod_data:
            self.report({'INFO'}, "No Geometry Nodes bakes found on active object.")
            return {'FINISHED'}

        state = getattr(obj, "gn_bake_state", None)

        if self.action in ('REBAKE_STALE', 'BAKE_ALL'):
            target_items = []
            for m in mod_data:
                m_name = m["modifier_name"]
                for b in m["bakes"]:
                    if not b.get("is_group") and b.get("is_connected") and not b.get("is_muted") and b.get("bake_id"):
                        if self.action == 'REBAKE_STALE' and b.get("cache_state") != 'STALE':
                            continue
                        target_items.append((m_name, b.get("bake_id"), b.get("name"), b.get("mode") == 'STILL'))

            if not target_items:
                msg = "No stale bake nodes found to rebake." if self.action == 'REBAKE_STALE' else "No active connected bake nodes found."
                self.report({'INFO'}, msg)
                return {'FINISHED'}

            orig_frame = context.scene.frame_current
            baked_count = 0
            total_duration = 0.0

            try:
                for idx, (m_name, bake_id, b_name, is_still) in enumerate(target_items):
                    target_frame = orig_frame
                    if is_still and state:
                        if state.static_bake_mode == 'ORIGINAL':
                            rec = state.get_recorded_frame(m_name, bake_id)
                            if rec is not None:
                                target_frame = rec
                        elif state.static_bake_mode == 'GLOBAL':
                            target_frame = state.static_global_frame

                    if is_still and context.scene.frame_current != target_frame:
                        context.scene.frame_set(target_frame)

                    t0 = time.time()
                    try:
                        bpy.ops.object.geometry_node_bake_single(
                            session_uid=obj.session_uid,
                            modifier_name=m_name,
                            bake_id=bake_id
                        )
                        dur = time.time() - t0
                        total_duration += dur
                        if state:
                            state.set_bake_timestamp(m_name, bake_id)
                            state.set_bake_duration(m_name, bake_id, dur)
                            if is_still:
                                state.set_recorded_frame(m_name, bake_id, target_frame)
                        baked_count += 1
                    except Exception as e:
                        self.report({'WARNING'}, f"Failed baking {b_name}: {e}")
            finally:
                if context.scene.frame_current != orig_frame:
                    context.scene.frame_set(orig_frame)

            self.report({'INFO'}, f"Successfully baked {baked_count} node(s) in dependency order ({total_duration:.1f}s).")
            return {'FINISHED'}

        elif self.action in ('CLEAR_STALE', 'CLEAR_ALL'):
            target_items = []
            for m in mod_data:
                m_name = m["modifier_name"]
                for b in m["bakes"]:
                    if not b.get("is_group") and b.get("bake_id"):
                        if self.action == 'CLEAR_STALE' and b.get("cache_state") != 'STALE':
                            continue
                        if self.action == 'CLEAR_ALL' and not b.get("has_cache"):
                            continue
                        target_items.append((m_name, b.get("bake_id"), b.get("name")))

            if not target_items:
                msg = "No stale bake nodes found to clear." if self.action == 'CLEAR_STALE' else "No cached bake nodes found to clear."
                self.report({'INFO'}, msg)
                return {'FINISHED'}

            cleared_count = 0
            for idx, (m_name, bake_id, b_name) in enumerate(target_items):
                try:
                    bpy.ops.object.geometry_node_bake_delete_single(
                        session_uid=obj.session_uid,
                        modifier_name=m_name,
                        bake_id=bake_id
                    )
                    if state:
                        state.clear_bake_timestamp(m_name, bake_id)
                    cleared_count += 1
                except Exception as e:
                    self.report({'WARNING'}, f"Failed clearing {b_name}: {e}")

            self.report({'INFO'}, f"Cleared cache for {cleared_count} bake node(s).")
            return {'FINISHED'}

        return {'FINISHED'}


class OBJECT_OT_gn_bake_toggle_group(Operator):
    bl_idname = "object.gn_bake_toggle_group"
    bl_label = "Toggle Group Collapse"
    bl_description = "Expand or collapse this group hierarchy"
    bl_options = {'INTERNAL'}

    modifier_name: StringProperty(name="Modifier Name", default="")
    group_key: StringProperty(name="Group Key", default="")

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}
        state = getattr(obj, "gn_bake_state", None)
        if not state:
            return {'CANCELLED'}

        collapsed = set(state.collapsed_groups.split(";")) if state.collapsed_groups else set()
        key = f"{self.modifier_name}::{self.group_key}"
        if key in collapsed:
            collapsed.remove(key)
        else:
            collapsed.add(key)
        state.collapsed_groups = ";".join(filter(None, collapsed))
        return {'FINISHED'}


classes = (
    OBJECT_OT_gn_bake_navigate_to,
    OBJECT_OT_gn_bake_single_action,
    OBJECT_OT_gn_bake_batch_action,
    OBJECT_OT_gn_bake_toggle_group,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            pass


def unregister():
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
