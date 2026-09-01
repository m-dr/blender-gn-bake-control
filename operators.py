import bpy
from bpy.types import Operator
from bpy.props import StringProperty


class OBJECT_OT_gn_bake_navigate_to(Operator):
    bl_idname = "object.gn_bake_navigate_to"
    bl_label = "Navigate to Node"
    bl_description = "Focus and navigate to this modifier or bake node in the Node Editor"
    bl_options = {'REGISTER', 'UNDO'}

    modifier_name: StringProperty(name="Modifier Name", default="")
    node_tree_name: StringProperty(name="Node Tree Name", default="")
    node_name: StringProperty(name="Node Name", default="")

    def execute(self, context):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}

        # 1. If modifier is specified, set active in modifier stack
        if self.modifier_name:
            mod = obj.modifiers.get(self.modifier_name)
            if mod:
                try:
                    obj.modifiers.active = mod
                except Exception:
                    pass

        # 2. Find target node tree
        ntree = None
        if self.node_tree_name:
            ntree = bpy.data.node_groups.get(self.node_tree_name)
        elif self.modifier_name:
            mod = obj.modifiers.get(self.modifier_name)
            if mod and mod.type == 'NODES':
                ntree = mod.node_group

        # 3. Find Node Editor space in active screen
        node_space = None
        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        node_space = space
                        break
                if node_space:
                    break

        if node_space and ntree:
            node_space.tree_type = 'GeometryNodeTree'
            node_space.node_tree = ntree

            if self.node_name:
                target_node = ntree.nodes.get(self.node_name)
                if target_node:
                    for n in ntree.nodes:
                        n.select = False
                    target_node.select = True
                    ntree.nodes.active = target_node
                    self.report({'INFO'}, f"Selected '{target_node.name}' in '{ntree.name}'")
                    return {'FINISHED'}

            self.report({'INFO'}, f"Navigated to '{ntree.name}'")
            return {'FINISHED'}

        if not node_space:
            self.report({'WARNING'}, "No Geometry Node Editor is open on screen.")
            return {'CANCELLED'}

        return {'FINISHED'}


classes = (
    OBJECT_OT_gn_bake_navigate_to,
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
