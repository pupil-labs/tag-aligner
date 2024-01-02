import cv2
import numpy as np

from scipy.spatial.transform import Rotation

class Transformation:
	def __init__(self, position=None, rotation=None):
		if position is None:
			position = np.array([0.0, 0.0, 0.0])

		if rotation is None:
			rotation = Rotation([0.0, 0.0, 0.0, 1.0])

		self.position = np.copy(position.ravel())
		self.rotation = Rotation.from_quat(rotation.as_quat())

	def to_matrix(self):
		transformation_matrix = np.eye(4)
		transformation_matrix[:3, :3] = self.rotation.as_matrix()
		transformation_matrix[:3, 3] = self.position

		return transformation_matrix

	def relative_to(self, reference):
		my_matrix = self.to_matrix()
		ref_matrix = reference.to_matrix()

		my_rotation = my_matrix[:3, :3]
		my_translation = my_matrix[:3, 3]

		ref_rotation = ref_matrix[:3, :3]
		ref_translation = ref_matrix[:3, 3]

		relative_rotation = ref_rotation.T @ my_rotation
		relative_translation = ref_rotation.T @ (my_translation - ref_translation)

		result = np.eye(4)
		result[:3, :3] = relative_rotation
		result[:3, 3] = relative_translation

		return Transformation.from_matrix(result)

	@staticmethod
	def from_matrix(matrix):
		translation = matrix[:3, 3]
		rotation = Rotation.from_matrix(matrix[:3, :3])

		return Transformation(translation, rotation)

	def __repr__(self):
		pos = [f'{z:0.3f}' for z in self.position]
		rot = [f'{z:0.3f}' for z in self.rotation.as_quat()]
		return f'[{", ".join(pos)}], [{", ".join(rot)}]'

	def copy(self):
		return Transformation(self.position, self.rotation)

	def apply(self, matrix):
		return Transformation.from_matrix(np.linalg.inv(matrix) @ self.to_matrix())

def cv_space_to_3d_space(transform):
	pos = transform.position.copy()
	pos[1] *= -1

	euler = transform.rotation.as_euler('xyz')
	euler[1] *= -1
	euler[2] *= -1
	return Transformation(
		pos,
		Rotation.from_euler('xyz', euler)
	)


def rodrigues_to_rotation(rotation_rod):
	rotation_matrix, _ = cv2.Rodrigues(rotation_rod)

	return Rotation.from_matrix(rotation_matrix)


def point_distance(a, b):
	return np.linalg.norm(a-b)


def transform_by_reference(obj_b, obj_a, parent_a=None):
	if parent_a is None:
		parent_a = obj_a

	parent_matrix = parent_a.to_matrix()
	obj_a_local_matrix = obj_a.to_matrix()

	to_parent_trans_matrix = np.dot(parent_matrix, np.linalg.inv(obj_a_local_matrix))

	obj_b_local_matrix = obj_b.to_matrix()

	obj_b_in_parent_matrix = np.dot(to_parent_trans_matrix, obj_b_local_matrix)

	result = Transformation.from_matrix(obj_b_in_parent_matrix)
	result.rotation = result.rotation.inv()

	return result



def get_proxied_transform(local_transformation, world_transformation):
	pa = np.dot(
		world_transformation.to_matrix(),
		np.linalg.inv(local_transformation.to_matrix())
	)

	transform = Transformation.from_matrix(pa)
	transform.rotation = transform.rotation.inv()

	return transform


def do_proxy_transform(local_transform, proxy_transform):
	rm = np.dot(proxy_transform.to_matrix(), local_transform.to_matrix())

	result = Transformation.from_matrix(rm)
	result.setRotation(result.rotation.inv())

	return result



def find_transformation_matrix(source_transformation, target_transformation):
	source_matrix = source_transformation.to_matrix()
	target_matrix = target_transformation.to_matrix()

	# Calculate the inverse of the source transformation
	source_inverse = np.linalg.inv(source_matrix)
	target_inverse = np.linalg.inv(target_matrix)

	# Calculate the transformation matrix
	transformation_matrix = np.dot(source_inverse, target_inverse)
	#transformation_matrix = np.dot(source_inverse, target_matrix)

	return transformation_matrix
