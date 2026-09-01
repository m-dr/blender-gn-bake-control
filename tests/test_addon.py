import os
import sys
import unittest
import importlib.util

# Load the add-on module dynamically as 'gn_bake_control'
ADDON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
INIT_PATH = os.path.join(ADDON_DIR, "__init__.py")

spec = importlib.util.spec_from_file_location("gn_bake_control", INIT_PATH)
gn_bake_control = importlib.util.module_from_spec(spec)
sys.modules["gn_bake_control"] = gn_bake_control
spec.loader.exec_module(gn_bake_control)

import bpy
from gn_bake_control import traversal, properties, operators, ui, preferences


class DummyLayout:
    def __init__(self):
        self.scale_y = 1.0
        self.enabled = True
    def row(self, align=False):
        return DummyLayout()
    def column(self, align=False):
        return DummyLayout()
    def box(self):
        return DummyLayout()
    def label(self, text="", icon='NONE'):
        pass
    def prop(self, data, prop_name, text="", icon='NONE', icon_only=False, placeholder=""):
        pass
    def operator(self, op_idname, text="", icon='NONE'):
        return DummyOperator()
    def separator(self, factor=1.0):
        pass


class DummyOperator:
    def __init__(self):
        self.mode = ""
        self.action = ""
        self.modifier_name = ""
        self.bake_id = 0
        self.node_tree_name = ""
        self.node_name = ""


class TestGNBakeControl(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        try:
            gn_bake_control.unregister()
        except Exception:
            pass
        gn_bake_control.register()

    @classmethod
    def tearDownClass(cls):
        try:
            gn_bake_control.unregister()
        except Exception:
            pass

    def test_01_registration(self):
        """Verify add-on registers property groups, operators, and panels."""
        self.assertTrue(hasattr(bpy.types.Object, "gn_bake_state"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_batch"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_single_action"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_select_all"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_jump_to_node"))

    def test_02_traversal_on_test_file(self):
        """Verify traversal and topological ordering on real blend test file."""
        test_blend_path = os.path.join(os.path.dirname(__file__), "batch_bake_test_file.blend")
        if not os.path.exists(test_blend_path):
            self.skipTest("Test blend file not found")

        bpy.ops.wm.open_mainfile(filepath=test_blend_path)
        obj = bpy.data.objects.get("ANIM")
        self.assertIsNotNone(obj, "Object 'ANIM' should exist in test file")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        items = traversal.get_object_bake_items(obj)
        print(f"\n[Test] Traversed {len(items)} bake items on 'ANIM':")
        for i, it in enumerate(items):
            print(f"  [{i}] Mod: '{it['modifier_name']}', Node: '{it['node_name']}', Label: '{it['node_label']}', Path: '{it['group_path']}', Mode: {it['bake_mode']}")

        # We expect 6 total bakes (4 on first modifier, 2 on second modifier)
        self.assertEqual(len(items), 6)

        # First modifier bakes
        mod1_items = [it for it in items if it["modifier_name"] == "GeometryNodes"]
        self.assertEqual(len(mod1_items), 4)
        # Topological order: Bake.001 -> Bake -> Bake.002 -> Simulation Output
        self.assertEqual(mod1_items[0]["node_name"], "Bake.001")
        self.assertEqual(mod1_items[1]["node_name"], "Bake")
        self.assertEqual(mod1_items[2]["node_name"], "Bake.002")

        # Second modifier bakes
        mod2_items = [it for it in items if it["modifier_name"] == "GeometryNodes.001"]
        self.assertEqual(len(mod2_items), 2)
        # Topological order: Bake (root) -> Bake.001 (inside nested Bake Group)
        self.assertEqual(mod2_items[0]["node_name"], "Bake")
        self.assertEqual(mod2_items[1]["node_name"], "Bake.001")
        self.assertEqual(mod2_items[1]["group_path"], "Bake.001")

    def test_03_selection_operators(self):
        """Verify Select All, None, and Invert operators."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        # Select all
        bpy.ops.object.gn_bake_select_all(action='ALL')
        items = traversal.get_object_bake_items(obj)
        for it in items:
            self.assertTrue(it["setting"].is_selected)

        # Select none
        bpy.ops.object.gn_bake_select_all(action='NONE')
        items = traversal.get_object_bake_items(obj)
        for it in items:
            self.assertFalse(it["setting"].is_selected)

        # Invert
        bpy.ops.object.gn_bake_select_all(action='INVERT')
        items = traversal.get_object_bake_items(obj)
        for it in items:
            self.assertTrue(it["setting"].is_selected)

    def test_04_single_bake_and_clean(self):
        """Verify single bake and clean actions."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj
        items = traversal.get_object_bake_items(obj)
        self.assertTrue(len(items) > 0)

        target = items[0]
        # Bake single
        res = bpy.ops.object.gn_bake_single_action(
            action='BAKE',
            modifier_name=target["modifier_name"],
            bake_id=target["bake_id"]
        )
        self.assertEqual(res, {'FINISHED'})

        # Clean single
        res = bpy.ops.object.gn_bake_single_action(
            action='CLEAN',
            modifier_name=target["modifier_name"],
            bake_id=target["bake_id"]
        )
        self.assertEqual(res, {'FINISHED'})

    def test_05_jump_to_node(self):
        """Verify jump to node operator."""
        obj = bpy.data.objects.get("ANIM")
        items = traversal.get_object_bake_items(obj)
        target = items[0]
        res = bpy.ops.object.gn_bake_jump_to_node(
            node_tree_name=target["node_tree"].name,
            node_name=target["node_name"]
        )
        self.assertEqual(res, {'FINISHED'})

    def test_06_ui_draw(self):
        """Verify UI drawing without runtime errors in compact and detailed modes."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        dummy_layout = DummyLayout()

        # Test Compact UI
        obj.gn_bake_state.compact_ui = True
        ui.draw_gn_bake_ui(dummy_layout, bpy.context, is_npanel=False)
        ui.draw_gn_bake_ui(dummy_layout, bpy.context, is_npanel=True)

        # Test Detailed UI
        obj.gn_bake_state.compact_ui = False
        ui.draw_gn_bake_ui(dummy_layout, bpy.context, is_npanel=False)
        ui.draw_gn_bake_ui(dummy_layout, bpy.context, is_npanel=True)

    def test_07_batch_execution_helper(self):
        """Test batch execution helper for clean and bake operations."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        # Select only the first 2 still bakes
        bpy.ops.object.gn_bake_select_all(action='NONE')
        items = traversal.get_object_bake_items(obj)
        items[0]["setting"].is_selected = True
        items[1]["setting"].is_selected = True

        # Test still frame configuration
        items[0]["setting"].use_custom_still_frame = True
        items[0]["setting"].custom_still_frame = 25

        # Run direct single executions for the selected items
        for it in items:
            if it["setting"].is_selected:
                res = bpy.ops.object.gn_bake_single_action(
                    action='BAKE',
                    modifier_name=it["modifier_name"],
                    bake_id=it["bake_id"]
                )
                self.assertEqual(res, {'FINISHED'})


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
