import bpy
from bpy.types import Operator
from bpy.props import StringProperty, IntProperty, EnumProperty


def find_group_chain(current_tree, target_tree, visited=None):
    """
    Recursively find the sequence of (sub_tree, group_node) leading from current_tree to target_tree.
    """
    if not current_tree or not target_tree:
        return None
    if visited is None:
        visited = set()
    if current_tree in visited:
        return None
    visited.add(current_tree)

    if current_tree == target_tree:
        return []

    for node in current_tree.nodes:
        if node.type == 'GROUP' and getattr(node, "node_tree", None):
            if node.node_tree == target_tree:
                return [(node.node_tree, node)]
            sub_chain = find_group_chain(node.node_tree, target_tree, visited)
            if sub_chain is not None:
                return [(node.node_tree, node)] + sub_chain
    return None


class OBJECT_OT_gn_bake_navigate_to(Operator):
    bl_idname = "object.gn_bake_navigate_to"
    bl_label = "Navigate to Node"
    bl_description = "Focus, navigate to, and frame this modifier or bake node in the Geometry Node Editor"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_name: StringProperty(name="Modifier Name", default="")
    node_tree_name: StringProperty(name="Node Tree Name", default="")
    node_name: StringProperty(name="Node Name", default="")

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

        if not root_tree:
            self.report({'WARNING'}, "No node tree found to navigate to.")
            return {'CANCELLED'}

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

                # Switch tree type and root node tree
                space.tree_type = 'GeometryNodeTree'
                space.node_tree = root_tree

                # Build sub-group breadcrumb path if target is a sub-group
                if ntree and ntree != root_tree:
                    chain = find_group_chain(root_tree, ntree)
                    if chain:
                        for sub_tree, g_node in chain:
                            try:
                                space.path.append(sub_tree, node=g_node)
                            except Exception:
                                pass

                active_tree = ntree if ntree else root_tree

                if self.node_name and active_tree:
                    target_node = active_tree.nodes.get(self.node_name)
                    if target_node:
                        for n in active_tree.nodes:
                            n.select = False
                        target_node.select = True
                        active_tree.nodes.active = target_node

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

                        self.report({'INFO'}, f"Framed '{target_node.name}' in '{active_tree.name}'")
                        return {'FINISHED'}

                area.tag_redraw()

                # Frame all in node tree if navigating to modifier
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

                self.report({'INFO'}, f"Navigated to '{root_tree.name}'")
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

        try:
            state = getattr(obj, "gn_bake_state", None)
            if self.action == 'BAKE':
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

                if state:
                    state.set_bake_timestamp(self.modifier_name, self.bake_id)
                self.report({'INFO'}, f"Baked node (ID {self.bake_id}) in {self.modifier_name}")
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
