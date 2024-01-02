import csv
import sys
from pathlib import Path


from PySide6.QtWidgets import (
	QApplication,
	QWidget,
	QHBoxLayout, QVBoxLayout
)
from PySide6.QtCore import (
	Qt,
	QUrl,
)
from PySide6.QtGui import (
	QVector3D,
	QKeyEvent,
	QQuaternion,
)

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.Qt3DExtras import Qt3DExtras
from PySide6.Qt3DCore import Qt3DCore
from PySide6.Qt3DRender import Qt3DRender


class PlaybackApp(QApplication):
	def __init__(self):
		super().__init__()

		self.window = PlaybackWindow()
		self.window.show()

	def load_recording(self, path):
		print('Loading', path)
		videos = list(path.glob('*.mp4'))
		video_file = videos[0]
		self.window.video_widget.load(video_file)

		pose_file = path / 'aligned_poses.csv'
		self.window.scene_widget.load_poses(pose_file)

	def load_scene(self, path):
		print('Load scene', path)
		self.window.scene_widget.load_scene(path)

	def play(self):
		self.window.video_widget.player.play()


class PlaybackWindow(QWidget):
	def __init__(self):
		super().__init__()

		self.video_widget = VideoPlayerWidget()
		self.scene_widget = ScenePlayerWidget()

		self.setLayout(QHBoxLayout())
		self.layout().addWidget(self.video_widget)
		self.layout().addWidget(self.scene_widget)

		self.video_widget.player.positionChanged.connect(self.scene_widget.seek_to_time)

	def keyPressEvent(self, event):
		if isinstance(event, QKeyEvent):
			step = 0.05
			if event.key() == Qt.Key_W:
				self.scene_widget.move(0, 0, -step)
			elif event.key() == Qt.Key_S:
				self.scene_widget.move(0, 0, step)
			elif event.key() == Qt.Key_A:
				self.scene_widget.move(-step, 0, 0)
			elif event.key() == Qt.Key_D:
				self.scene_widget.move(step, 0, 0)
			elif event.key() == Qt.Key_Space:
				self.scene_widget.move(0, step, 0)
			elif event.key() == Qt.Key_Control:
				self.scene_widget.move(0, -step, 0)



class VideoPlayerWidget(QWidget):
	def __init__(self):
		super().__init__()

		self.player = QMediaPlayer()
		self.player_widget = QVideoWidget()
		self.player.setVideoOutput(self.player_widget)

		self.setLayout(QVBoxLayout())
		self.layout().addWidget(self.player_widget)

		self.setMinimumSize(200, 200)

	def load(self, path):
		self.player.setSource(QUrl.fromLocalFile(str(path)))

	def play(self):
		self.player.play()


class ScenePlayerWidget(QWidget):
	def __init__(self):
		super().__init__()

		self.scene_viewer = SceneViewer()
		self.scene_viewer_widget = self.createWindowContainer(self.scene_viewer)

		self.setLayout(QVBoxLayout())
		self.layout().addWidget(self.scene_viewer_widget, stretch=3)

		self.setMinimumSize(200, 200)
		self.poses = []

		self.installEventFilter(self)

	def load_scene(self, path):
		self.scene_viewer.scene.setSource(QUrl.fromLocalFile(str(path)))
		print('loaded scene', path)

	def load_poses(self, path):
		with path.open('r') as csv_file:
			reader = csv.DictReader(csv_file)
			self.poses = []
			for row in reader:
				row = {k:float(v) for k,v in row.items()}
				self.poses.append(row)

		print(len(self.poses), 'poses loaded')

	def seek_to_time(self, timestamp_ms):
		idx = self.find_index_by_timestamp(timestamp_ms/1000.0)
		pose = self.poses[idx]
		position = QVector3D(
			pose['translation_x'],
			pose['translation_y'],
			pose['translation_z']
		)
		rotation = QQuaternion(
			pose['rotation_w'],
			pose['rotation_x'],
			pose['rotation_y'],
			pose['rotation_z']
		)
		self.scene_viewer.set_camera_pose(position, rotation)
		print(idx, self.scene_viewer.camera_transform.translation())


	def find_index_by_timestamp(self, timestamp):
		left_idx = 0
		right_idx = len(self.poses)-1
		while right_idx - left_idx > 1:
			mid_idx = (left_idx + right_idx) // 2

			if timestamp < self.poses[mid_idx]['start_timestamp']:
				right_idx = mid_idx
			elif timestamp > self.poses[mid_idx]['end_timestamp']:
				left_idx = mid_idx
			else:
				break

		return mid_idx

	def move(self, x, y, z):
		self.scene_viewer.camera().translateWorld(QVector3D(x, y, z))
		print(self.scene_viewer.camera().position())

class SceneViewer(Qt3DExtras.Qt3DWindow):
	def __init__(self):
		super().__init__()

		self.defaultFrameGraph().setClearColor("black")
		self.defaultFrameGraph().setFrustumCullingEnabled(False)

		self.camera().lens().setPerspectiveProjection(132, 1.0, 0.01, 1000)
		self.camera().setPosition(QVector3D(0, 1, 1))
		for component in self.camera().components():
			if isinstance(component, Qt3DCore.QTransform):
				self.camera_transform = component
				break

		self.root_entity = Qt3DCore.QEntity()
		self.scene = Qt3DRender.QSceneLoader()
		self.root_entity.addComponent(self.scene)

		self.light_entity = Qt3DCore.QEntity(self.root_entity)
		self.light = Qt3DRender.QPointLight(self.light_entity)
		self.light.setIntensity(5)
		self.light_transform = Qt3DCore.QTransform()
		self.light_transform.setTranslation(QVector3D(1, 1, 1))
		self.light_entity.addComponent(self.light)
		self.light_entity.addComponent(self.light_transform)

		self.setRootEntity(self.root_entity)

	def resizeEvent(self, event):
		self.camera().setAspectRatio(self.width() / self.height())

	def set_camera_pose(self, position, rotation):
		self.camera_transform.setTranslation(position)
		self.camera_transform.setRotation(rotation)


if __name__ == '__main__':
	app = PlaybackApp()
	app.load_recording(Path(sys.argv[1]))
	app.load_scene(Path(sys.argv[2]))
	app.play()
	app.exec()
