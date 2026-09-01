import bpy
from bpy.types import Operator
from bpy.props import StringProperty


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

        # 3. Find Node Editor space, area, and window region in active screen
        target_space = None
        target_area = None
        target_region = None

        for area in context.screen.areas:
            if area.type == 'NODE_EDITOR':
                target_area = area
                for space in area.spaces:
                    if space.type == 'NODE_EDITOR':
                        target_space = space
                        break
                for region in area.regions:
                    if region.type == 'WINDOW':
                        target_region = region
                        break
                if target_space:
                    break

        if not target_space:
            self.report({'WARNING'}, "No Geometry Node Editor is open on screen.")
            return {'CANCELLED'}

        if ntree:
            target_space.tree_type = 'GeometryNodeTree'
            target_space.node_tree = ntree

            if self.node_name:
                target_node = ntree.nodes.get(self.node_name)
                if target_node:
                    for n in ntree.nodes:
                        n.select = False
                    target_node.select = True
                    ntree.nodes.active = target_node

                    # Focus view (Numpad .) onto the selected node
                    if not bpy.app.background and target_area and target_region:
                        with context.temp_override(area=target_area, region=target_region, space_data=target_space):
                            try:
                                bpy.ops.node.view_selected()
                            except Exception:
                                pass

                    self.report({'INFO'}, f"Framed '{target_node.name}' in '{ntree.name}'")
                    return {'FINISHED'}

            # Frame all in node tree if only navigating to modifier
            if not bpy.app.background and target_area and target_region:
                with context.temp_override(area=target_area, region=target_region, space_data=target_space):
                    try:
                        bpy.ops.node.view_all()
                    except Exception:
                        pass

            self.report({'INFO'}, f"Navigated to '{ntree.name}'")
            return {'FINISHED'}

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
