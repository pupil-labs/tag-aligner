bl_info = {
    "name": "Tag Aligner Render",
    "author": "Rob Ennis",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "category": "Object",
    "warning": "Requires installation of dependencies",
}

import os
import bpy
import mathutils
import math
import json
from mathutils import Vector
from itertools import chain

import numpy as np
import pandas as pd

from bpy.utils import resource_path
import pathlib


def find_nearest(array, value):
    idx = np.searchsorted(array, value, side="left")
    if idx > 0 and (idx == len(array) or math.fabs(value - array[idx-1]) < math.fabs(value - array[idx])):
        return idx-1
    else:
        return idx
    

def select_single_obj(single_obj):
    for obj in bpy.data.objects:
        obj.select_set(False)

    single_obj.select_set(True)
    bpy.context.view_layer.objects.active = single_obj


def disable_objs(objs):
    for obj in objs:
        obj.hide_render = True
        obj.hide_viewport = True
        obj.hide_select = True
        

def enable_objs(objs):
    for obj in objs:
        obj.hide_render = False
        obj.hide_viewport = False
        obj.hide_select = False


def raycast_cone(dg, ro, head_quat, gaze_quat):
    rs = np.linspace(0, 2.5, 5)
    thetas = np.linspace(0, 2*np.pi, 12)

    t_closest = 1e20
    closest_isect = None
    for theta in thetas:
        for r in rs:
            h_a = r*np.cos(theta)
            v_a = r*np.sin(theta)
            
            h_disp = mathutils.Quaternion((0.0, 0.0, 1.0), math.radians(h_a))
            v_disp = mathutils.Quaternion((1.0, 0.0, 0.0), math.radians(v_a))
            rd = head_quat @ v_disp @ h_disp @ gaze_quat @ Vector((0.0, 1.0, 0.0))

            rd = rd / np.linalg.norm(rd)

            isect = bpy.context.scene.ray_cast(dg, ro, rd)

            if isect[0]:
                h = isect[1]
                t = np.linalg.norm(h - ro)
                
                if t < t_closest:
                    closest_isect = isect
                    h_closest = h
                    t_closest = t

    return closest_isect


addon_keymaps = []

def register():
    bpy.types.Scene.rec_dir = bpy.props.StringProperty(name="rec_dir",
                                                       description="Directory with Neon recording to animate",
                                                       default="")
    bpy.types.Scene.gaze_cone_intersect = bpy.props.BoolProperty(name="gaze_cone_intersect",
                                                       description="When enabled, intersect gaze cone with scene")
    bpy.utils.register_class(OperatorAnimateNeon)
    bpy.utils.register_class(OperatorImportMeshes)
    bpy.utils.register_class(PANEL_PT_AnimateNeon)
    bpy.types.VIEW3D_MT_object.append(menu_func)
    
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = wm.keyconfigs.addon.keymaps.new(name='Object Mode',
                                             space_type='EMPTY')
        kmi = km.keymap_items.new(OperatorAnimateNeon.bl_idname,
                                  'T',
                                  'PRESS',
                                  ctrl=True,
                                  shift=True)
        addon_keymaps.append((km, kmi))
    
    
def unregister():
    del bpy.types.Scene.rec_dir
    del bpy.types.Scene.gaze_cone_intersect
    bpy.utils.unregister_class(OperatorAnimateNeon)
    bpy.utils.unregister_class(OperatorImportMeshes)
    bpy.utils.unregister_class(PANEL_PT_AnimateNeon)
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    
    addon_keymaps.clear()


def menu_func(self, context):
    self.layout.operator(ObjectAnimateNeon.bl_idname)    


class PANEL_PT_AnimateNeon(bpy.types.Panel):
    """ Tag Aligner - Animate Neon """
    # bl_idname = "SCENE_PT_neon"
    bl_label = "Animate Neon Object with Tag Aligner data"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Tag Aligner - Neon"
    
    
    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="Recording directory:")

        row = layout.row()
        row.prop(scene, "rec_dir")

        layout.label(text="Frames to animate:")

        row = layout.row()
        row.prop(scene, "frame_start")
        row.prop(scene, "frame_end")

        layout.label(text="Import meshes:")
        
        row = layout.row()
        row.operator(OperatorImportMeshes.bl_idname)
        
        layout.label(text="Intersection method:")
        
        row = layout.row()
        row.prop(scene, "gaze_cone_intersect")

        layout.label(text="Animate:")
        
        row = layout.row()
        row.operator(OperatorAnimateNeon.bl_idname)


class OperatorImportMeshes(bpy.types.Operator):
    """ Tag Aligner - Import Eyetracker Meshes """
    bl_idname = "object.import_pl_meshes"
    bl_label = "Import eyetracker meshes"
    bl_options = {'REGISTER', 'UNDO'}
    
    
    def __init__(self):
        self.user_dir = pathlib.Path(bpy.utils.resource_path('USER'))


    def execute(self, context):
        addon_file_path =  self.user_dir / "scripts" / "addons"
        bpy.ops.import_scene.gltf(filepath=str(addon_file_path / "tag_aligner_assets" / "tag_aligner_pl_objs.gltf"))
        
        self.report({'INFO'}, "Tag Aligner: Loaded eyetracker meshes.")
        
        return {'FINISHED'}


class OperatorAnimateNeon(bpy.types.Operator):
    """ Tag Aligner - Animate Neon """
    bl_idname = "object.neon_animate"
    bl_label = "Apply Tag Aligner data"
    bl_options = {'REGISTER', 'UNDO'}

    
    def __init__(self):
        self.directory = bpy.context.scene.rec_dir

        self.report({'INFO'}, "Tag Aligner: Initializing...")

        # get start ts
        with open(os.path.join(self.directory, "info.json")) as f:
            info = json.load(f)
            self.start_ts = info["start_time"]

        # load gaze - 8, 9
        self.gaze_df = pd.read_csv(os.path.join(self.directory, 'gaze.csv'))
        self.gaze_df["timestamp [s]"] = (self.gaze_df["timestamp [ns]"] - self.start_ts) * 1e-9

        # load poses from tag aligner
        self.poses_df = pd.read_csv(os.path.join(self.directory, 'aligned_poses.csv'))

        self.report({'INFO'}, "Tag Aligner: Loaded start_ts, gaze, and pose data.")

        self.head_curve = []
        self.head_fcurve = []
                
        self.init_quat_jan = mathutils.Quaternion((0.0, 0.0, 0.1, -0.995))
        self.init_quat_ray = mathutils.Quaternion((0.707, -0.707, 0.0, 0.0))
        self.init_quat_fru = mathutils.Quaternion((0.658, 0.658, 0.259, -0.259))
        self.init_quat_gzcirc = mathutils.Quaternion((0.707, 0.707, 0.0, 0.0))
                        
        self.obj_curves = {}
        
        self.report({'INFO'}, "Tag Aligner: Blender obj refs prepared.")

        self.fps = 29.97 # as reported by ffmpeg
        self.spf = 1.0/self.fps
        self.rec_start_s = self.start_ts * 1e-9
        self.gaze_start_s = self.gaze_df["timestamp [ns]"][0] * 1e-9
        self.head_start_s = self.poses_df["start_timestamp"][0]
        self.data_start_s = self.head_start_s if self.head_start_s < self.gaze_start_s else self.gaze_start_s

        self.n_buffer_frames = np.round(self.data_start_s * self.fps).astype(np.int64)

        self.last_frame = self.n_buffer_frames + len(self.poses_df)     
        
        self.report({'INFO'}, "Tag Aligner: Temporal context calculated. Preparing keyframe loop...")


    def create_curve(self, context):
        # already loaded and created curve for head trajectory
        if context.scene.objects.find('head_trajectory') > -1:
            self.report({'INFO'}, "Tag Aligner: Using current head trajectory curve.")

            self.head_curve = context.scene.objects['head_trajectory']
            self.pl_objs.append(self.head_curve)
            return
        
        xs = self.poses_df["translation_x"]
        ys = self.poses_df["translation_y"]
        zs = self.poses_df["translation_z"]
        
        crv = bpy.data.curves.new('crv', 'CURVE')
        crv.dimensions = '3D'
        spline = crv.splines.new(type='NURBS')
        spline.use_endpoint_u = True
        spline.use_endpoint_v = True
        
        spline.points.add(len(self.poses_df) - 1)
        for p, x, y, z in zip(spline.points, xs, ys, zs):    
            # tag_aligner -> blender
            y, z = z, -1.0*y
            p.co = ([x, y, z, 1.0]) # 4 coords?
        
        
        self.head_curve = bpy.data.objects.new('head_trajectory', crv)
        self.pl_objs.append(self.head_curve)
        
        self.head_curve.data.extrude = 0.01
        
        # start with curve hidden
        self.head_curve.data.bevel_factor_end = 0.0
        
        bpy.data.scenes[0].collection.objects.link(self.head_curve)
        
        # solidify curve so it looks a bit better, more visible
        select_single_obj(self.head_curve)
        bpy.ops.object.modifier_add(type='SOLIDIFY')
        context.object.modifiers["Solidify"].thickness = 0.01
        context.object.modifiers["Solidify"].offset = 0
        
        self.report({'INFO'}, "Tag Aligner: Created new head trajectory curve.")


    def apply_curve_material(self):
        # create curve material if not already created.
        # otherwise, assign and return
        if bpy.data.materials.get("curve_material") is None:
            crv_mat = bpy.data.materials.new("curve_material")
        
            bpy.data.materials["curve_material"].use_nodes = True
            bpy.data.materials["curve_material"].node_tree.nodes["Principled BSDF"].inputs[0].default_value = (1, 0.236721, 0.0176297, 1)
            bpy.data.materials["curve_material"].node_tree.nodes["Principled BSDF"].inputs[26].default_value = (1, 0.111108, 0.0123341, 1)
            # bpy.data.materials["curve_material"].node_tree.nodes["Principled BSDF"].inputs[27].default_value = 0.8
            bpy.data.materials["curve_material"].node_tree.nodes["Principled BSDF"].inputs[2].default_value = 1
        else:
            crv_mat = bpy.data.materials["curve_material"]


        crv = self.head_curve
        if crv.data.materials:
            crv.data.materials[0] = crv_mat
        else:
            crv.data.materials.append(crv_mat)

        self.report({'INFO'}, "Tag Aligner: Applied curve material.")


    def init_fcurves(self, context):
        for action in bpy.data.actions:
            bpy.data.actions.remove(action)
        
        for obj in self.pl_objs:            
            if obj is context.scene.objects['head_trajectory']:
                if obj.data.animation_data is not None:
                    obj.animation_data_clear()
                
                obj.data.animation_data_create()
                obj.data.animation_data.action = bpy.data.actions.new(name=obj.name + 'Action')

                bevel_end_fcurve = obj.data.animation_data.action.fcurves.new(data_path='bevel_factor_end')
                
                bevel_end_fcurve.keyframe_points.add(context.scene.frame_end)
                for kf in bevel_end_fcurve.keyframe_points:
                    kf.interpolation = 'CONSTANT'

                self.head_fcurve = bevel_end_fcurve
            else:
                if obj.animation_data is not None:
                    obj.animation_data_clear()
                
                obj.animation_data_create()
                obj.animation_data.action = bpy.data.actions.new(name=obj.name + 'Action')
            
                loc_fcurves = [obj.animation_data.action.fcurves.new('location', index=index) for index in range(3)]
                rot_fcurves = [obj.animation_data.action.fcurves.new('rotation_quaternion', index=index) for index in range(4)]
                scale_fcurves = [obj.animation_data.action.fcurves.new('scale', index=index) for index in range(3)]
                
                for fcurve in chain(loc_fcurves, rot_fcurves, scale_fcurves):
                    fcurve.keyframe_points.add(context.scene.frame_end)
                    for kf in fcurve.keyframe_points:
                        kf.interpolation = 'CONSTANT'
                
                self.obj_curves[obj.name] = {
                    'location': loc_fcurves,
                    'rotation': rot_fcurves,
                    'scale': scale_fcurves,
                }
                
    
    def insert_fcurve(self, obj, frame_num, location, rotation, scale):
        obj_fcurves = self.obj_curves[obj.name]
        
        for lc in range(3):
            obj_fcurves['location'][lc].keyframe_points[frame_num].co_ui = [frame_num, location[lc]]
        
        for rc in range(4):
            obj_fcurves['rotation'][rc].keyframe_points[frame_num].co_ui = [frame_num, rotation[rc]]
        
        for sc in range(3):
            obj_fcurves['scale'][sc].keyframe_points[frame_num].co_ui = [frame_num, scale[sc]]


    def build_pl_obj_dict(self):
        self.JAN = bpy.context.scene.objects['Neon-JAN']
        self.gzray = bpy.context.scene.objects['GazeRay']
        self.fru = bpy.context.scene.objects['Frustum']
        self.fruframe = bpy.context.scene.objects['FrustumFrame']
        self.gzcirc = bpy.context.scene.objects['Gaze']

        self.pl_objs = [self.JAN,
                        self.gzray,
                        self.fru,
                        self.fruframe,
                        self.gzcirc,]


    def execute(self, context):
        self.build_pl_obj_dict()
            
        # due to Blender constraints, need to init head curve here
        self.create_curve(context)
        self.apply_curve_material()

        # dance needed to make sure that head trajectory curve can be properly animated
        select_single_obj(self.head_curve)
        self.head_curve.data.extrude = 0.01
        self.head_curve.data.bevel_factor_end = 0.0
        context.object.data.bevel_factor_end = 0.0
        
        self.init_fcurves(context)
        
        context.view_layer.update()
        dg = context.view_layer.depsgraph
        dg.update()
        
        disable_objs(self.pl_objs)
        
        self.report({'INFO'}, "Tag Aligner: Curve parameters and depsgraph prepared. Entering keyframe loop...")

        for frame_num in range(context.scene.frame_end):
            if frame_num < self.n_buffer_frames:
                x = self.poses_df["translation_x"][0]
                y = self.poses_df["translation_y"][0]
                z = self.poses_df["translation_z"][0]

                # tag_aligner -> blender
                coordinates = [x, z, -1.0*y]

                rot_x = self.poses_df["rotation_x"][0]
                rot_y = self.poses_df["rotation_y"][0]
                rot_z = self.poses_df["rotation_z"][0]
                rot_w = self.poses_df["rotation_w"][0]

                # tag_aligner -> blender
                head_quat = mathutils.Quaternion((rot_w, rot_x, rot_z, -1.0*rot_y))

                rot = head_quat @ self.init_quat_jan
                self.insert_fcurve(self.JAN, frame_num, coordinates, rot, [0.001, 0.001, 0.001])

                self.head_fcurve.keyframe_points[frame_num].co_ui = [frame_num, 0.0]
                
                fru_rot = head_quat @ self.init_quat_fru
                self.insert_fcurve(self.fru, frame_num, coordinates, fru_rot, [0.131666, 0.122527, 0.135845])

                fruframe_rot = head_quat @ self.init_quat_fru
                self.insert_fcurve(self.fruframe, frame_num, coordinates, fruframe_rot, [0.131666, 0.122527, 0.135845])
                
                gzray_rot = head_quat @ self.init_quat_ray
                self.insert_fcurve(self.gzray, frame_num, coordinates, gzray_rot, [0.8, 0.8, 0.0])
                
                gzcirc_rot = self.init_quat_gzcirc
                self.insert_fcurve(self.gzcirc, frame_num, [-1000, -1000, -1000], gzcirc_rot, [0.081241, 0.081241, 0.081241])
            else:
                data_frame = frame_num - self.n_buffer_frames
                
                corr_ts = self.spf * (frame_num - 2)
#                pose_idx = np.searchsorted(self.poses_df["start_timestamp"], corr_ts, side="left")
                pose_idx = find_nearest(self.poses_df["start_timestamp"], corr_ts)
                
                x = self.poses_df["translation_x"][pose_idx]
                y = self.poses_df["translation_y"][pose_idx]
                z = self.poses_df["translation_z"][pose_idx]

                # tag_aligner -> blender
                coordinates = [x, z, -1.0*y]

                rot_x = self.poses_df["rotation_x"][pose_idx]
                rot_y = self.poses_df["rotation_y"][pose_idx]
                rot_z = self.poses_df["rotation_z"][pose_idx]
                rot_w = self.poses_df["rotation_w"][pose_idx]

                # tag_aligner -> blender
                head_quat = mathutils.Quaternion((rot_w, rot_x, rot_z, -1.0*rot_y))

                gaze_idxs = (self.gaze_df["timestamp [s]"] > self.poses_df["start_timestamp"][pose_idx]) & (self.gaze_df["timestamp [s]"] < self.poses_df["end_timestamp"][pose_idx])
                curr_ts = self.poses_df["start_timestamp"][pose_idx]

                elv = np.mean(self.gaze_df[gaze_idxs]["elevation [deg]"])
                azi = np.mean(self.gaze_df[gaze_idxs]["azimuth [deg]"])

                # tag_aligner -> blender
                azi = mathutils.Quaternion((0.0, 0.0, 1.0), -1.0*math.radians(azi))
                elv = mathutils.Quaternion((1.0, 0.0, 0.0), math.radians(elv))
                gaze_quat = elv @ azi
                
                ro = Vector(coordinates)
                if bpy.context.scene.gaze_cone_intersect:
                    isect = raycast_cone(dg, ro, head_quat, gaze_quat)
                else:
                    rd = head_quat @ gaze_quat @ Vector((0.0, 1.0, 0.0))
                    rd = rd / np.linalg.norm(rd)
                    isect = bpy.context.scene.ray_cast(dg, ro, rd)
                    if not isect[0]:
                        isect = None

                t = 0.0
                norm_quat = []
                if isect is not None:
                    h = isect[1]
                    t = np.linalg.norm(h - ro)
                
                    n = isect[2]
                    v = Vector((0.0, 1.0, 0.0))
                    norm_quat = n.rotation_difference(v)


                rot = head_quat @ self.init_quat_jan
                self.insert_fcurve(self.JAN, frame_num, coordinates, rot, [0.001, 0.001, 0.001])
                
                self.head_fcurve.keyframe_points[frame_num].co_ui = [frame_num, pose_idx/len(self.poses_df)]
                
                fru_rot = head_quat @ self.init_quat_fru
                self.insert_fcurve(self.fru, frame_num, coordinates, fru_rot, [0.131666, 0.122527, 0.135845])

                fruframe_rot = head_quat @ self.init_quat_fru
                self.insert_fcurve(self.fruframe, frame_num, coordinates, fruframe_rot, [0.131666, 0.122527, 0.135845])
                
                gzray_zscale = 0.0
                if isect is not None:
                    gzray_zscale = t
                else:
                    gzray_zscale = 100.0
                
                gzray_rot = head_quat @ gaze_quat @ self.init_quat_ray
                self.insert_fcurve(self.gzray, frame_num, coordinates, gzray_rot, [0.8, 0.8, gzray_zscale])
                
                gzcirc_location, gzcirc_rot = [], []
                if isect is not None:
                    gaze_dir = head_quat @ gaze_quat @ Vector((0.0, 1.0, 0.0))            
                    gaze_dir = gaze_dir/np.linalg.norm(gaze_dir)
                    
                    gzcirc_rot = head_quat @ gaze_quat @ self.init_quat_gzcirc
                    gzcirc_location = ro + Vector(t*gaze_dir)
                else:
                    gzcirc_location = [-1000, -1000, -1000]
                    gzcirc_rot = self.init_quat_gzcirc

                self.insert_fcurve(self.gzcirc, frame_num, gzcirc_location, gzcirc_rot, [0.081241, 0.081241, 0.081241])


        enable_objs(self.pl_objs)
        context.scene.frame_set(0)
        
        self.report({'INFO'}, "Tag Aligner: Prepared {} keyframes.".format(context.scene.frame_end))
        
        return {'FINISHED'}


if __name__ == "__main__":
    register()