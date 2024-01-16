from pathlib import Path
import json
import pickle

from tqdm import tqdm

from pupil_apriltags import Detector

import numpy as np
import cv2
from scipy.spatial.transform import Rotation

import decord

from .maths import (
	point_distance,
	rodrigues_to_rotation,
	Transformation
)

import pickle

SAVE_POSE_PAIRS = True

def calc_correction(bad, good):
	good_inv = np.linalg.inv(good.to_matrix())
	return bad.to_matrix() @ good_inv


def calculate_alignment(recording_path, reference_tags):
	scan_video = list(recording_path.glob('*.mp4'))[0]
	pose_df = pickle.load(open(recording_path / 'poses.p', 'br'))

	scene_camera = json.load(open(recording_path / 'scene_camera.json', 'r'))
	camera_distortion = np.array(scene_camera['distortion_coefficients']).ravel()
	camera_matrix = np.matrix(scene_camera['camera_matrix'])
	camera_params = [
		scene_camera['camera_matrix'][0][0], #fx
		scene_camera['camera_matrix'][1][1], #fy
		scene_camera['camera_matrix'][0][2], #cx
		scene_camera['camera_matrix'][1][2], #cy
	]
	print('Camera params =', camera_params)
	print('Distortion    =', camera_distortion)

	at_detector = Detector()
	pose_pairs = []
	pose_idx = 0

	pose_pair_file = (recording_path / 'pose-pairs.pickle')
	if SAVE_POSE_PAIRS and pose_pair_file.exists():
		print('Loading pose pairs pickle', pose_pair_file)
		with pose_pair_file.open('rb') as input_file:
			pose_pairs = pickle.load(input_file)

	else:
		video_reader = decord.VideoReader(str(scan_video), ctx=decord.cpu(0))
		for frame_idx,frame in enumerate(tqdm(video_reader)):
			frame_time = video_reader.get_frame_timestamp(frame_idx)[0]
			frame = frame.asnumpy()

			frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

			while pose_idx < len(pose_df)-1 and pose_df[pose_idx]['end_timestamp'] < frame_time:
				pose_idx += 1

			if frame_time < pose_df[pose_idx]['start_timestamp']:
				# there's a gap in the poses, so we must wait for the video to catch up to the poses
				continue
			elif frame_time > pose_df[pose_idx]['end_timestamp']:
				# we ran out of poses, no need to continue looking
				break

			detected_tags = at_detector.detect(frame_gray)
			if len(detected_tags) == 0:
				continue

			cam_pose = Transformation(
				np.array([
					pose_df[pose_idx]['translation_x'],
					pose_df[pose_idx]['translation_y'],
					pose_df[pose_idx]['translation_z'],
				]),
				rodrigues_to_rotation(np.array([
					pose_df[pose_idx]['rotation_x'],
					pose_df[pose_idx]['rotation_y'],
					pose_df[pose_idx]['rotation_z'],
				]))
			)

			for detected_tag in detected_tags:
				if detected_tag.tag_id not in reference_tags:
					continue

				ref_tag = reference_tags[detected_tag.tag_id]
				tag_points_3d = np.array([
					[-ref_tag["size"]/2,  ref_tag["size"]/2, 0], # BL
					[ ref_tag["size"]/2,  ref_tag["size"]/2, 0], # BR
					[ ref_tag["size"]/2, -ref_tag["size"]/2, 0], # TL
					[-ref_tag["size"]/2, -ref_tag["size"]/2, 0], # TR
				])


				# SOLVEPNP_IPPE_SQUARE returns 2 solutions for rotation/position/error.
				# First one always has smallest error
				ok, (tag_rotation,_), (tag_position,_), (error,_) = cv2.solvePnPGeneric(
					tag_points_3d,
					detected_tag.corners,
					camera_matrix,
					camera_distortion,
					flags = cv2.SOLVEPNP_IPPE_SQUARE
				)

				if not ok:
					continue

				tag_pose = Transformation(tag_position, rodrigues_to_rotation(tag_rotation))
				cam_pose_relative_to_tag = Transformation().relative_to(tag_pose)
				correction = calc_correction(Transformation(), ref_tag["pose"])
				cam_pose_real = cam_pose_relative_to_tag.apply(correction)

				# save pose pair info
				pose_pairs.append({
					'frame_idx': frame_idx,
					'pose_idx': pose_idx,
					'cam_pose': cam_pose,
					'tag_pose': tag_pose,
					'tag_pose_err': error,
					'cam_pose_real': cam_pose_real
				})

	print('Found', len(pose_pairs), 'pose pairs')

	print('Calculating scale...')
	# Find pair of points with largest difference
	# Use that to calculate scale factor
	id_a = id_b = None
	max_distance_virt = 0
	for pair_idx_a, pair_a in enumerate(pose_pairs):
		for pair_idx_b in range(pair_idx_a+1, len(pose_pairs)):
			pair_b = pose_pairs[pair_idx_b]

			distance = point_distance(pair_a['cam_pose'].position, pair_b['cam_pose'].position)
			if distance > max_distance_virt:
				max_distance_virt = distance
				id_a = pair_idx_a
				id_b = pair_idx_b

	if id_a is not None:
		# Find scale
		cam_pose = Transformation()

		cam_pose_a = pose_pairs[id_a]['cam_pose_real']
		cam_pose_b = pose_pairs[id_b]['cam_pose_real']
		a_pose_idx = pose_pairs[id_a]['pose_idx']
		b_pose_idx = pose_pairs[id_b]['pose_idx']

		max_distance_real = point_distance(cam_pose_a.position, cam_pose_b.position)
		virt_to_real_scale = max_distance_real / max_distance_virt
		print('Max distance traveled', a_pose_idx, 'to', b_pose_idx, f'virt = {max_distance_virt:0.3f}, real={max_distance_real:.03f}')
		print('Scale =', virt_to_real_scale)

		# find pose pair with smallest tag pose error
		smallest_error = float('inf')
		best_pose_pair = None
		for pp in pose_pairs:
			if pp["tag_pose_err"] < smallest_error:
				smallest_error = pp["tag_pose_err"]
				best_pose_pair = pp

		# use that pose to calculate the correction matrix
		cam_pose_orig = best_pose_pair['cam_pose'].copy()
		cam_pose_orig.position *= virt_to_real_scale
		cam_pose_real = best_pose_pair['cam_pose_real']
		corrective_matrix = calc_correction(cam_pose_orig, cam_pose_real)


		return {
			'scale': virt_to_real_scale,
			'corrective_matrix': corrective_matrix,
		}


if __name__ == '__main__':
	import sys

	np.set_printoptions(formatter={'float_kind':"{:+.3f}".format})

	reference_tags = {}
	with open(sys.argv[2], "r") as input_file:
		for tag_info in json.load(input_file):
			reference_tags[tag_info["id"]] = {
				"size": tag_info["size"],
				"pose": Transformation(
					np.array(tag_info["position"]),
					Rotation.from_quat(tag_info["rotation"]),
				)
			}

	alignment_info = calculate_alignment(
		recording_path = Path(sys.argv[1]),
		reference_tags = reference_tags
	)
	alignment_info['corrective_matrix'] = alignment_info['corrective_matrix'].tolist()

	if len(sys.argv) > 3:
		output_file = sys.argv[3]
		print('Writing', output_file)
		with open(output_file, 'w') as output_file:
			json.dump(alignment_info, output_file, indent=4)
	else:
		json.dumps(alignment_info, indent=4)
