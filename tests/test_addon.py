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
from gn_bake_control import traversal, ui, operators, preferences


class DummyLayout:
    def __init__(self):
        self.scale_y = 1.0
        self.enabled = True
        self.active = True
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
        self.modifier_name = ""
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
        """Verify add-on registers panels and operators cleanly."""
        self.assertTrue(hasattr(ui, "DATA_PT_gn_bake_control"))
        self.assertTrue(hasattr(ui, "VIEW3D_PT_gn_bake_control"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_navigate_to"))

    def test_02_traversal_and_frame_info(self):
        """Verify active bake nodes listing and frame metadata."""
        test_blend_path = os.path.join(os.path.dirname(__file__), "batch_bake_test_file.blend")
        if not os.path.exists(test_blend_path):
            self.skipTest("Test blend file not found")

        bpy.ops.wm.open_mainfile(filepath=test_blend_path)
        obj = bpy.data.objects.get("ANIM")
        self.assertIsNotNone(obj, "Object 'ANIM' should exist in test file")
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        mod_data = traversal.get_object_bake_list(obj, scene=bpy.context.scene)
        self.assertEqual(len(mod_data), 2)

        # Mod 1: GeometryNodes (4 bakes)
        mod1 = mod_data[0]
        self.assertEqual(mod1["modifier_name"], "GeometryNodes")
        self.assertTrue(mod1["is_enabled"])
        self.assertEqual(len(mod1["bakes"]), 4)
        self.assertEqual(mod1["bakes"][0]["name"], "Bake.001")
        self.assertTrue("Still" in mod1["bakes"][0]["frame_info"])
        self.assertEqual(mod1["bakes"][2]["name"], "Bake.002")
        self.assertTrue("Range" in mod1["bakes"][2]["frame_info"])

        # Mod 2: GeometryNodes.001 (2 bakes)
        mod2 = mod_data[1]
        self.assertEqual(mod2["modifier_name"], "GeometryNodes.001")
        self.assertEqual(len(mod2["bakes"]), 2)
        self.assertEqual(mod2["bakes"][1]["path"], "Bake.001 > Bake.001")

    def test_03_disabled_modifier_status(self):
        """Verify disabled modifier status is properly tracked."""
        obj = bpy.data.objects.get("ANIM")
        mod_gn = obj.modifiers["GeometryNodes"]
        mod_gn.show_viewport = False

        mod_data = traversal.get_object_bake_list(obj)
        self.assertFalse(mod_data[0]["is_enabled"])

        mod_gn.show_viewport = True
        mod_data = traversal.get_object_bake_list(obj)
        self.assertTrue(mod_data[0]["is_enabled"])

    def test_04_navigation_operator(self):
        """Verify navigation operator focusing modifier and nested bake nodes."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        # Navigate to nested node Bake.001 in Bake Group
        res = bpy.ops.object.gn_bake_navigate_to(
            modifier_name="GeometryNodes.001",
            node_tree_name="Bake Group",
            node_name="Bake.001"
        )
        self.assertEqual(res, {'FINISHED'})

    def test_05_ui_draw(self):
        """Verify UI drawing without any runtime errors."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        dummy_layout = DummyLayout()
        ui.draw_gn_bake_ui(dummy_layout, bpy.context)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
