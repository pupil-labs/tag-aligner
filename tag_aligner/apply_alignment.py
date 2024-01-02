import csv
import json
import pickle
import sys

from pathlib import Path

import numpy as np

from maths import (
	Transformation,
	rodrigues_to_rotation
)


def apply_alignment(recording_path, scale, corrective_matrix):
	pose_df = pickle.load(open(recording_path / 'poses.p', 'br'))

	output_file = (recording_path / 'aligned_poses.csv')
	print('Writing', output_file)

	with output_file.open('w') as csv_file:
		dict_writer = csv.DictWriter(csv_file, fieldnames=[
			'start_timestamp', 'end_timestamp',
			'translation_x', 'translation_y', 'translation_z',
			'rotation_x', 'rotation_y', 'rotation_z', 'rotation_w',
			'original_translation_x', 'original_translation_y', 'original_translation_z',
		])
		dict_writer.writeheader()

		for pose in pose_df:
			transform = Transformation(
				np.array([pose['rotation_x'], pose['rotation_y'], pose['rotation_z']]),
				rodrigues_to_rotation(np.array([pose['rotation_x'], pose['rotation_y'], pose['rotation_z']]))
			).apply(corrective_matrix)

			rotation = transform.rotation.as_quat()

			dict_writer.writerow({
				'start_timestamp': pose['start_timestamp'],
				'end_timestamp': pose['end_timestamp'],
				'translation_x': transform.position[0],
				'translation_y': transform.position[1],
				'translation_z': transform.position[2],
				'rotation_x': rotation[0],
				'rotation_y': rotation[1],
				'rotation_z': rotation[2],
				'rotation_w': rotation[3],
				'original_translation_x': pose['translation_x'],
				'original_translation_y': pose['translation_y'],
				'original_translation_z': pose['translation_z'],
			})


if __name__ == '__main__':
	np.set_printoptions(formatter={'float_kind':"{:+.3f}".format})

	with open(sys.argv[2], 'r') as json_file:
		alignment_info = json.load(json_file)
		alignment_info['corrective_matrix'] = np.array(alignment_info['corrective_matrix'])

	apply_alignment(
		recording_path = Path(sys.argv[1]),
		scale = alignment_info['scale'],
		corrective_matrix = alignment_info['corrective_matrix'],
	)
