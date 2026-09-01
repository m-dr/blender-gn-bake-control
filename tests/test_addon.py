import os
import sys
import time
import unittest
import importlib.util

addon_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pkg_name = "gn_bake_control"

if pkg_name not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        pkg_name,
        os.path.join(addon_dir, "__init__.py"),
        submodule_search_locations=[addon_dir]
    )
    gn_bake_control = importlib.util.module_from_spec(spec)
    sys.modules[pkg_name] = gn_bake_control
    spec.loader.exec_module(gn_bake_control)
else:
    gn_bake_control = sys.modules[pkg_name]

import bpy
from gn_bake_control import traversal, ui, operators, preferences, properties


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

    def operator(self, op_idname, text="", icon='NONE', **kwargs):
        return DummyOperator()

    def separator(self, factor=1.0):
        pass


class DummyOperator:
    def __init__(self):
        self.action = "BAKE"
        self.modifier_name = ""
        self.node_tree_name = ""
        self.node_name = ""
        self.bake_id = 0
        self.group_key = ""
        self.group_chain_json = ""


class TestGNBakeControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gn_bake_control
        try:
            gn_bake_control.register()
        except Exception:
            pass

    @classmethod
    def tearDownClass(cls):
        import gn_bake_control
        try:
            gn_bake_control.unregister()
        except Exception:
            pass

    def test_01_registration(self):
        """Verify add-on registers panels and operators cleanly."""
        self.assertTrue(hasattr(ui, "DATA_PT_gn_bake_control"))
        self.assertTrue(hasattr(ui, "VIEW3D_PT_gn_bake_control"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_navigate_to"))
        self.assertTrue(hasattr(bpy.ops.object, "gn_bake_single_action"))
        self.assertTrue(hasattr(bpy.types.Object, "gn_bake_state"))

    def test_02_simulation_and_group_encapsulation(self):
        """Verify nested group bakes and simulation zone outputs are properly encapsulated."""
        test_blend_path = os.path.join(os.path.dirname(__file__), "batch_bake_test_file.blend")
        if not os.path.exists(test_blend_path):
            self.skipTest("Test blend file not found")

        bpy.ops.wm.open_mainfile(filepath=test_blend_path)
        obj = bpy.data.objects.get("ANIM")
        cache_dir = os.path.join(os.path.dirname(test_blend_path), "blendcache_batch_bake_test_file", "ANIM_GeometryNodes")
        for b_id in ["74436161", "581967954", "1651669316"]:
            p = os.path.join(cache_dir, b_id)
            os.makedirs(p, exist_ok=True)
            with open(os.path.join(p, "data.blob"), "w") as f:
                f.write("test")

        mod_data = traversal.get_object_bake_list(obj, scene=bpy.context.scene)
        self.assertEqual(len(mod_data), 2)

        # Mod 1: GeometryNodes (4 active bakes in DAG execution order)
        mod1 = mod_data[0]
        self.assertEqual(mod1["modifier_name"], "GeometryNodes")
        self.assertEqual(mod1["connected_count"], 4)

        # Verify hierarchical stage tags
        actual_bakes = [b for b in mod1["bakes"] if not b.get("is_group")]
        self.assertEqual(len(actual_bakes), 4)

        tags = [b["num_tag"] for b in actual_bakes]
        names = [b["name"] for b in actual_bakes]

        self.assertEqual(tags[0], "1.1")
        self.assertEqual(names[0], "Bake.001")

        self.assertEqual(tags[1], "1.2")
        self.assertEqual(names[1], "Bake")

        self.assertEqual(tags[2], "1")
        self.assertEqual(names[2], "Simulation Output")

        self.assertEqual(tags[3], "3")
        self.assertEqual(names[3], "Bake.002")

        # Cache check
        self.assertTrue(actual_bakes[0]["has_cache"])
        self.assertTrue(actual_bakes[1]["has_cache"])

    def test_03_disconnected_node_handling(self):
        """Verify disconnected nodes are flagged and numbered above active stages."""
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

        # Last item should be the disconnected Bake.001 with number above max active stage
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
        """Verify muting a parent group properly mutes all nested bakes and filters when disconnected hidden."""
        obj = bpy.data.objects.get("ANIM")
        mod_gn = obj.modifiers["GeometryNodes"]
        group_node = mod_gn.node_group.nodes["G_Temporal Smooth Position"]

        group_node.mute = True
        mod_data = traversal.get_object_bake_list(obj, show_disconnected=True)
        sim_bake = [b for b in mod_data[0]["bakes"] if b["name"] == "Simulation Output"][0]
        self.assertTrue(sim_bake["is_muted"])

        # When show_disconnected is False, muted bake is filtered out
        mod_data_filtered = traversal.get_object_bake_list(obj, show_disconnected=False)
        sim_bakes_filtered = [b for b in mod_data_filtered[0]["bakes"] if b["name"] == "Simulation Output"]
        self.assertEqual(len(sim_bakes_filtered), 0)

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

        # Nested group check
        nested_bake = [b for b in mod2["bakes"] if b["name"] == "Bake.001" and not b.get("is_group")][0]
        self.assertEqual(nested_bake["group_name"], "Bake Group")
        self.assertEqual(nested_bake["num_tag"], "1")

        # Test navigation into nested group
        res = bpy.ops.object.gn_bake_navigate_to(
            modifier_name="GeometryNodes.001",
            node_tree_name="Bake Group",
            node_name="Bake.001"
        )
        self.assertEqual(res, {'FINISHED'})

    def test_08_single_bake_and_clear_operators(self):
        """Verify single bake and clear actions and group containment."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        mod_data = traversal.get_object_bake_list(obj)
        actual_bakes = [b for b in mod_data[0]["bakes"] if not b.get("is_group")]

        # Check group containment metadata
        sim_bake = [b for b in actual_bakes if b["name"] == "Simulation Output"][0]
        self.assertEqual(sim_bake["group_name"], "G_Temporal Smooth Position")

        target_bake = actual_bakes[0]
        # Test clear action
        res_clear = bpy.ops.object.gn_bake_single_action(
            action='CLEAR',
            modifier_name=mod_data[0]["modifier_name"],
            bake_id=target_bake["bake_id"]
        )
        self.assertEqual(res_clear, {'FINISHED'})

        # Test bake action
        res_bake = bpy.ops.object.gn_bake_single_action(
            action='BAKE',
            modifier_name=mod_data[0]["modifier_name"],
            bake_id=target_bake["bake_id"]
        )
        self.assertEqual(res_bake, {'FINISHED'})

    def test_09_group_collapse_toggle(self):
        """Verify expanding and collapsing group hierarchies."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        state = obj.gn_bake_state
        self.assertEqual(state.collapsed_groups, "")

        # Collapse group
        res = bpy.ops.object.gn_bake_toggle_group(
            modifier_name="GeometryNodes",
            group_key="::G_Temporal Smooth Position"
        )
        self.assertEqual(res, {'FINISHED'})
        self.assertIn("GeometryNodes::::G_Temporal Smooth Position", state.collapsed_groups)

        # Expand group
        res = bpy.ops.object.gn_bake_toggle_group(
            modifier_name="GeometryNodes",
            group_key="::G_Temporal Smooth Position"
        )
        self.assertEqual(res, {'FINISHED'})
        self.assertNotIn("GeometryNodes::::G_Temporal Smooth Position", state.collapsed_groups)

    def test_10_flatten_hierarchy_toggle(self):
        """Verify flattening hierarchy hides groups and draws cleanly."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj

        state = obj.gn_bake_state
        state.flatten_hierarchy = True
        self.assertTrue(state.flatten_hierarchy)

        dummy_layout = DummyLayout()
        ui.draw_gn_bake_ui(dummy_layout, bpy.context)
        state.flatten_hierarchy = False

    def test_11_stale_downstream_invalidation(self):
        """Verify downstream bakes are marked STALE when upstream bake is newer."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj
        state = obj.gn_bake_state

        # Set upstream Bake.001 (ID 74436161) to timestamp 200, downstream Bake.002 (ID 1651669316) to timestamp 100
        state.set_bake_timestamp("GeometryNodes", 74436161, timestamp=200.0)
        state.set_bake_timestamp("GeometryNodes", 1651669316, timestamp=100.0)

        mod_data = traversal.get_object_bake_list(obj)
        bakes = mod_data[0]["bakes"]

        b_upstream = [b for b in bakes if b["name"] == "Bake.001" and not b.get("is_group")][0]
        b_downstream = [b for b in bakes if b["name"] == "Bake.002" and not b.get("is_group")][0]

        self.assertEqual(b_upstream["cache_state"], 'BAKED')
        self.assertEqual(b_upstream["status_icon"], 'CHECKMARK')

        self.assertEqual(b_downstream["cache_state"], 'STALE')
        self.assertEqual(b_downstream["status_icon"], 'FILE_REFRESH')

        # When downstream Bake.002 is rebaked with latest timestamp, it becomes BAKED again
        state.set_bake_timestamp("GeometryNodes", 1651669316, timestamp=time.time() + 1000.0)
        mod_data2 = traversal.get_object_bake_list(obj)
        b_downstream2 = [b for b in mod_data2[0]["bakes"] if b["name"] == "Bake.002" and not b.get("is_group")][0]
        self.assertEqual(b_downstream2["cache_state"], 'BAKED')
        self.assertEqual(b_downstream2["status_icon"], 'CHECKMARK')


    def test_12_batch_bake_actions(self):
        """Verify batch bake operators execute successfully."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj
        
        # Test CLEAR_STALE
        res1 = bpy.ops.object.gn_bake_batch_action(action='CLEAR_STALE')
        self.assertEqual(res1, {'FINISHED'})
        
        # Test CLEAR_ALL
        res2 = bpy.ops.object.gn_bake_batch_action(action='CLEAR_ALL')
        self.assertEqual(res2, {'FINISHED'})
        
    def test_13_stats_and_compact_frames(self):
        """Verify compact frame formatting, stats durations, and static frame modes."""
        obj = bpy.data.objects.get("ANIM")
        bpy.context.view_layer.objects.active = obj
        state = obj.gn_bake_state
        
        # Test compact frame format (e.g. '25' instead of 'Frame 25')
        bpy.context.scene.frame_set(42)
        mod_data = traversal.get_object_bake_list(obj, scene=bpy.context.scene)
        bakes = mod_data[0]["bakes"]
        b_still = [b for b in bakes if b["mode"] == 'STILL' and not b.get("is_group")][0]
        self.assertNotIn("Frame", b_still["frame_info"])
        
        # Test stats duration tracking
        state.set_bake_duration("GeometryNodes", 74436161, 0.45)
        self.assertAlmostEqual(state.get_bake_duration("GeometryNodes", 74436161), 0.45, places=2)
        
        state.show_stats = True
        self.assertTrue(state.show_stats)
        
        # Test static bake mode properties
        state.static_bake_mode = 'GLOBAL'
        state.static_global_frame = 50
        self.assertEqual(state.static_bake_mode, 'GLOBAL')
        self.assertEqual(state.static_global_frame, 50)
        
        dummy_layout = DummyLayout()
        ui.draw_gn_bake_ui(dummy_layout, bpy.context)


if __name__ == "__main__":
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

