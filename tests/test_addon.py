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
from gn_bake_control import traversal, ui, preferences


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
        return DummyLayout()
    def separator(self, factor=1.0):
        pass


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
        """Verify add-on registers panels and preferences cleanly."""
        self.assertTrue(hasattr(ui, "DATA_PT_gn_bake_control"))
        self.assertTrue(hasattr(ui, "VIEW3D_PT_gn_bake_control"))

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

    def test_03_mute_filtering(self):
        """Verify muted nodes are automatically excluded from the active list."""
        obj = bpy.data.objects.get("ANIM")
        mod_gn = obj.modifiers["GeometryNodes"]
        target_node = mod_gn.node_group.nodes["Bake.001"]

        # Initial: 4 bakes
        mod_data = traversal.get_object_bake_list(obj)
        self.assertEqual(len(mod_data[0]["bakes"]), 4)

        # Mute node -> should drop to 3
        target_node.mute = True
        mod_data_muted = traversal.get_object_bake_list(obj)
        self.assertEqual(len(mod_data_muted[0]["bakes"]), 3)
        b_names = [b["name"] for b in mod_data_muted[0]["bakes"]]
        self.assertNotIn("Bake.001", b_names)

        # Unmute
        target_node.mute = False
        mod_data_unmuted = traversal.get_object_bake_list(obj)
        self.assertEqual(len(mod_data_unmuted[0]["bakes"]), 4)

    def test_04_ui_draw(self):
        """Verify UI drawing without any runtime errors."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        dummy_layout = DummyLayout()
        ui.draw_gn_bake_ui(dummy_layout, bpy.context)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
