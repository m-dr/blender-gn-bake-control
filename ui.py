import bpy
from bpy.types import Panel

from .traversal import get_object_bake_list
from .preferences import get_preferences


def draw_gn_bake_ui(layout, context):
    obj = context.active_object
    if not obj:
        layout.label(text="Select an object to inspect bakes", icon='INFO')
        return

    state = getattr(obj, "gn_bake_state", None)
    show_disconnected = state.show_disconnected if state else True

    mod_data = get_object_bake_list(obj, scene=context.scene, show_disconnected=show_disconnected)

    # Toolbar row with Disconnected nodes filter toggle
    row_tools = layout.row(align=True)
    if state:
        row_tools.prop(
            state,
            "show_disconnected",
            text="Show Disconnected / Stale",
            icon='HIDE_OFF' if state.show_disconnected else 'HIDE_ON'
        )

    if not mod_data:
        box = layout.box()
        box.label(text="No Geometry Nodes bake nodes on object.", icon='INFO')
        return

    for entry in mod_data:
        mod_name = entry["modifier_name"]
        is_enabled = entry.get("is_enabled", True)
        bakes = entry["bakes"]
        conn_count = entry.get("connected_count", len(bakes))
        dis_count = entry.get("disconnected_count", 0)

        box = layout.box()
        box.active = is_enabled

        # Modifier header
        head = box.row(align=True)
        mod_icon = 'NODETREE' if is_enabled else 'RESTRICT_VIEW_ON'
        head.label(text=f"{mod_name}", icon=mod_icon)

        count_label = f"({conn_count} Active" + (f", {dis_count} Disc)" if dis_count > 0 else ")")
        head.label(text=count_label)

        # Jump to modifier in Node Editor button
        op_mod_nav = head.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
        op_mod_nav.modifier_name = mod_name

        current_group_box = None
        current_group_name = None

        # Track sibling stages for visual grouping
        current_stage_box = None
        current_stage_id = None

        # Group items by base stage prefix for sibling nesting
        # e.g. "1.1" and "1.2" have base stage "1"
        stage_counts = {}
        for b in bakes:
            if not b.get("is_group"):
                tag = b.get("num_tag", "")
                parts = tag.split(".")
                if len(parts) >= 2:
                    base_stage = ".".join(parts[:-1])
                    stage_counts[base_stage] = stage_counts.get(base_stage, 0) + 1

        for b in bakes:
            # Handle Group Header items
            if b.get("is_group"):
                current_group_name = b.get("name")
                current_group_box = box.box()
                grp_head = current_group_box.row(align=True)
                grp_head.label(text=f"[{b['num_tag']}]  {b['name']}", icon='NODETREE')
                op_grp_nav = grp_head.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_grp_nav.modifier_name = mod_name
                op_grp_nav.node_tree_name = b.get("tree_name", "")
                op_grp_nav.node_name = b.get("node_name", "")
                current_stage_box = None
                current_stage_id = None
                continue

            group_name = b.get("group_name", "")
            if not group_name:
                current_group_box = None
                current_group_name = None

            parent_box = current_group_box if (current_group_box and group_name) else box

            # Check if this item belongs to a multi-sibling parallel branch stage
            tag = b.get("num_tag", "")
            parts = tag.split(".")
            base_stage = ".".join(parts[:-1]) if len(parts) >= 2 else None

            if base_stage and stage_counts.get(base_stage, 0) > 1:
                # Sibling branch stage
                if current_stage_id != base_stage:
                    current_stage_id = base_stage
                    current_stage_box = parent_box.box()
                    # Optional subtle branch stage label
                    branch_head = current_stage_box.row(align=True)
                    branch_head.label(text=f"Branch Stage [{base_stage}] ({stage_counts[base_stage]} Parallel Inputs)", icon='CON_FOLLOWPATH')
                target_container = current_stage_box
            else:
                current_stage_id = None
                current_stage_box = None
                target_container = parent_box

            row = target_container.row(align=True)

            is_conn = b.get("is_connected", True)
            is_muted = b.get("is_muted", False)

            # Dim row only if disconnected (muted nodes remain fully active for baking per Blender behavior)
            if not is_conn:
                row.active = False

            # Proportional split: Left (Status + Jump + Stage/Node), Right (Frame + Bake + Clear)
            split = row.split(factor=0.58, align=True)

            # Left section
            left = split.row(align=True)

            # Cache status indicator
            icon = 'CHECKMARK' if b["has_cache"] else 'RADIOBUT_OFF'
            left.label(text="", icon=icon)

            # Compact right arrow navigate & frame node button
            if b.get("node_name"):
                op_node_nav = left.operator("object.gn_bake_navigate_to", text="", icon='RIGHTARROW')
                op_node_nav.modifier_name = mod_name
                op_node_nav.node_tree_name = b.get("tree_name", "")
                op_node_nav.node_name = b.get("node_name", "")
            else:
                left.label(text="", icon='BLANK1')

            # Combined stage badge + node display name with tight spacing
            node_icon = 'AUTO' if b.get("is_simulation") else 'PHYSICS'
            display_text = f"[{b['num_tag']}]  {b['name']}" if b.get("num_tag") else b["name"]

            if not is_conn:
                display_text += " [Disc]"
            elif is_muted:
                display_text += " [Muted]"

            left.label(text=display_text, icon=node_icon)

            # Right section: Right-aligned Frame info + Action buttons
            right = split.row(align=True)
            right.alignment = 'RIGHT'

            frame_icon = 'IMAGE_DATA' if b["mode"] == 'STILL' else 'TIME'
            right.label(text=b["frame_info"], icon=frame_icon)

            # Bake action button (Text)
            bake_id = b.get("bake_id", 0)
            if bake_id:
                op_bake = right.operator("object.gn_bake_single_action", text="Bake")
                op_bake.action = 'BAKE'
                op_bake.modifier_name = mod_name
                op_bake.bake_id = bake_id

                # Clear cache action button (Trash can icon)
                sub_clear = right.row(align=True)
                sub_clear.enabled = b["has_cache"]
                op_clear = sub_clear.operator("object.gn_bake_single_action", text="", icon='TRASH')
                op_clear.action = 'CLEAR'
                op_clear.modifier_name = mod_name
                op_clear.bake_id = bake_id


class DATA_PT_gn_bake_control(Panel):
    bl_idname = "DATA_PT_gn_bake_control"
    bl_label = "GN Bake Control (DEV)"
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "modifier"
    bl_order = -100

    @classmethod
    def poll(cls, context):
        prefs = get_preferences(context)
        if prefs and not prefs.show_in_modifier_stack:
            return False
        return context.active_object is not None

    def draw(self, context):
        draw_gn_bake_ui(self.layout, context)


class VIEW3D_PT_gn_bake_control(Panel):
    bl_idname = "VIEW3D_PT_gn_bake_control"
    bl_label = "GN Bake Control (DEV)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "GN Bake (DEV)"

    @classmethod
    def poll(cls, context):
        prefs = get_preferences(context)
        if prefs and not prefs.show_in_3dview_sidebar:
            return False
        return context.active_object is not None

    def draw(self, context):
        draw_gn_bake_ui(self.layout, context)


classes = (
    DATA_PT_gn_bake_control,
    VIEW3D_PT_gn_bake_control,
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
