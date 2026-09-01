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
        self.alignment = 'LEFT'
    def row(self, align=False):
        return DummyLayout()
    def column(self, align=False):
        return DummyLayout()
    def split(self, factor=0.0, align=False):
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
        self.assertTrue(hasattr(bpy.types.Object, "gn_bake_state"))

    def test_02_simulation_and_group_encapsulation(self):
        """Verify nested group bakes and simulation zone outputs are properly encapsulated."""
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

        # Mod 1: GeometryNodes (4 bakes in exact execution order)
        mod1 = mod_data[0]
        self.assertEqual(mod1["modifier_name"], "GeometryNodes")
        self.assertEqual(len(mod1["bakes"]), 4)

        paths = [b["path"] for b in mod1["bakes"]]
        self.assertIn("G_Temporal Smooth Position > Simulation Output", paths)
        self.assertEqual(paths[0], "Bake.001")
        self.assertEqual(paths[1], "Bake")
        self.assertEqual(paths[2], "G_Temporal Smooth Position > Simulation Output")
        self.assertEqual(paths[3], "Bake.002")

        # Cache check: Bake.001 and Bake have disk cache
        self.assertTrue(mod1["bakes"][0]["has_cache"])
        self.assertTrue(mod1["bakes"][1]["has_cache"])

    def test_03_disconnected_node_handling(self):
        """Verify disconnected nodes are flagged and appended at the bottom."""
        obj = bpy.data.objects.get("ANIM")
        mod_gn = obj.modifiers["GeometryNodes"]
        bake_node = mod_gn.node_group.nodes["Bake.001"]

        # Disconnect all links from Bake.001
        for l in list(mod_gn.node_group.links):
            if l.to_node == bake_node or l.from_node == bake_node:
                mod_gn.node_group.links.remove(l)

        mod_data = traversal.get_object_bake_list(obj, show_disconnected=True)
        mod1 = mod_data[0]
        self.assertEqual(mod1["connected_count"], 3)
        self.assertEqual(mod1["disconnected_count"], 1)

        # Last item should be the disconnected Bake.001
        last_bake = mod1["bakes"][-1]
        self.assertEqual(last_bake["name"], "Bake.001")
        self.assertFalse(last_bake["is_connected"])

    def test_04_navigation_and_framing(self):
        """Verify navigation operator focusing and framing nodes."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        res = bpy.ops.object.gn_bake_navigate_to(
            modifier_name="GeometryNodes",
            node_tree_name="G_Temporal Smooth Position",
            node_name="Simulation Output"
        )
        self.assertEqual(res, {'FINISHED'})

    def test_05_ui_draw(self):
        """Verify UI drawing without any runtime errors."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        dummy_layout = DummyLayout()
        ui.draw_gn_bake_ui(dummy_layout, bpy.context)

    def test_06_group_mute_propagation(self):
        """Verify muting a parent group properly mutes all nested bakes."""
        obj = bpy.data.objects.get("ANIM")
        mod_gn = obj.modifiers["GeometryNodes"]
        group_node = mod_gn.node_group.nodes["G_Temporal Smooth Position"]

        group_node.mute = True
        mod_data = traversal.get_object_bake_list(obj)
        sim_bake = [b for b in mod_data[0]["bakes"] if b["name"] == "Simulation Output"][0]
        self.assertTrue(sim_bake["is_muted"])

        group_node.mute = False
        mod_data = traversal.get_object_bake_list(obj)
        sim_bake = [b for b in mod_data[0]["bakes"] if b["name"] == "Simulation Output"][0]
        self.assertFalse(sim_bake["is_muted"])

    def test_07_group_naming_and_subgroup_breadcrumbs(self):
        """Verify group names use node_tree.name and breadcrumbs are properly built."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        mod_data = traversal.get_object_bake_list(obj)
        mod2 = mod_data[1]
        self.assertEqual(mod2["modifier_name"], "GeometryNodes.001")
        # Should be 'Bake Group > Bake.001' not 'Bake.001 > Bake.001'
        self.assertEqual(mod2["bakes"][1]["path"], "Bake Group > Bake.001")

        # Test navigation into nested group
        res = bpy.ops.object.gn_bake_navigate_to(
            modifier_name="GeometryNodes.001",
            node_tree_name="Bake Group",
            node_name="Bake.001"
        )
        self.assertEqual(res, {'FINISHED'})


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
