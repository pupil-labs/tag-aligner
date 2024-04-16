import csv
import sys
import json
import struct
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QGridLayout, QHBoxLayout,
    QPushButton,
    QSlider,
    QGraphicsView,
    QGraphicsScene,
    QSizePolicy,
)
from PySide6.QtCore import (
    Qt,
    QUrl,
    QTimer,
    QRect,
)
from PySide6.QtGui import (
    QVector3D,
    QQuaternion,
    QPen,
    QColor,
)

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.Qt3DExtras import Qt3DExtras
from PySide6.Qt3DCore import Qt3DCore
from PySide6.Qt3DRender import Qt3DRender

from .maths import (
    Transformation,
    cv_space_to_qt3d_space
)

import numpy as np
from scipy.spatial.transform import Rotation


class PlaybackApp(QApplication):
    def __init__(self):
        super().__init__()

        self.window = PlaybackWindow()
        self.window.show()

        self.gazes = None

    def load_recording(self, path):
        videos = list(path.glob('*.mp4'))
        video_file = videos[0]
        self.window.video_widget.load(video_file)

        pose_file = path / 'aligned_poses.csv'
        self.window.scene_widget.load_poses(pose_file)

        with Path(path/'info.json').open('r') as recording_info_file:
            recording_info = json.load(recording_info_file)

        gaze_file = path / 'gaze.csv'
        with gaze_file.open('r') as csv_file:
            reader = csv.DictReader(csv_file)
            self.gazes = []
            for row in reader:
                for k in row:
                    if ' id' not in k:
                        row[k] = float(row[k])

                row['timestamp'] = (row['timestamp [ns]'] - recording_info['start_time']) / 1e9

                self.gazes.append(row)

        self.window.scene_widget.set_gazes(self.gazes)
        self.window.video_widget.set_gazes(self.gazes)

    def load_scene(self, path):
        self.window.scene_widget.load_scene(path)

    def play(self):
        self.window.video_widget.player.play()


class PlaybackWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.video_widget = VideoPlayerWidget()
        self.scene_widget = ScenePlayerWidget()

        self.controls = QWidget()
        self.controls.setLayout(QHBoxLayout())
        self.play_button = QPushButton("⏯️")
        self.time_slider = QSlider(Qt.Horizontal)
        self.controls.layout().addWidget(self.play_button)
        self.controls.layout().addWidget(self.time_slider)


        self.setLayout(QGridLayout())
        self.layout().addWidget(self.video_widget, 0, 0)
        self.layout().addWidget(self.scene_widget, 0, 1)
        self.layout().addWidget(self.controls, 1, 0, 1, 2)
        self.layout().setRowStretch(0, 1)

        self.play_button.clicked.connect(self.toggle_play)
        self.video_widget.player.positionChanged.connect(self.on_video_position_changed)
        self.video_widget.player.durationChanged.connect(self.time_slider.setMaximum)
        self.time_slider.sliderMoved.connect(self.video_widget.player.setPosition)

        self.resize(1600, 800)

    def toggle_play(self):
        self.video_widget.toggle_playback()

    def on_video_position_changed(self, time):
        self.scene_widget.seek_to_time(time)
        self.time_slider.setValue(time)


class VideoPlayerWidget(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.horizontalScrollBar().setDisabled(True)
        self.verticalScrollBar().setDisabled(True)

        self.player = QMediaPlayer()
        self.player.positionChanged.connect(self._on_video_position_changed)

        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        self.bg_rect = self.scene.addRect(QRect(-100, -100, 300, 300), QPen(QColor(0, 0, 0, 0)))

        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)

        pen = QPen(QColor(255, 0, 0, 100))
        pen.setWidth(20)
        self.gaze_circle = self.scene.addEllipse(-1000, -1000, 150, 150, pen)
        self.gaze_circle.setVisible(False)

        self.player.setVideoOutput(self.video_item)

        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.player.mediaStatusChanged.connect(lambda _: QTimer.singleShot(1000, self.fit_view))

        self.gazes = []

    def _on_video_position_changed(self, timestamp_ms):
        gaze_idx = find_gaze_index_by_timestamp(self.gazes, timestamp_ms/1000.0)
        if gaze_idx is None:
            self.set_gaze_point(None, None)
            return

        gaze = self.gazes[gaze_idx]
        self.set_gaze_point(gaze["gaze x [px]"], gaze["gaze y [px]"])


    def fit_view(self):
        if self.video_item.size() != self.video_item.nativeSize():
            w = self.video_item.nativeSize().width()
            h = self.video_item.nativeSize().height()
            self.video_item.setSize(self.video_item.nativeSize())
            self.bg_rect.setRect(QRect(-w, -h, w*3, h*3))

        self.fitInView(self.video_item, Qt.KeepAspectRatio)

    def resizeEvent(self, event):
        self.fit_view()

    def sizeHint(self):
        return None

    def load(self, path):
        self.player.setSource(QUrl.fromLocalFile(str(path)))

    def set_gazes(self, gazes):
        self.gazes = gazes

    def set_gaze_point(self, x, y):
        if x is None or y is None:
            self.gaze_circle.setVisible(False)
            return

        self.gaze_circle.setVisible(True)
        self.gaze_circle.setRect(
            x - self.gaze_circle.rect().width()/2,
            y - self.gaze_circle.rect().height()/2,
            self.gaze_circle.rect().width(),
            self.gaze_circle.rect().height(),
        )

    def play(self):
        self.player.play()

    def toggle_playback(self):
        if self.player.isPlaying():
            self.player.pause()
        else:
            self.player.play()


class SceneViewerWindow(Qt3DExtras.Qt3DWindow):
    def __init__(self):
        super().__init__()

        self.defaultFrameGraph().setClearColor(QColor(27, 30, 32))
        self.defaultFrameGraph().setFrustumCullingEnabled(False)

        self.root_entity = Qt3DCore.QEntity()
        self.scene = Qt3DRender.QSceneLoader()
        self.root_entity.addComponent(self.scene)

        self.subject_material = Qt3DExtras.QPhongMaterial()
        self.subject_material.setAmbient(QColor(128, 128, 128))

        self.ray_material = Qt3DExtras.QPhongMaterial()
        self.ray_material.setAmbient(QColor(255, 0, 0))

        self.subject_entity = Qt3DCore.QEntity(self.root_entity)
        self.subject_scene = Qt3DRender.QSceneLoader()
        self.subject_scene.statusChanged.connect(lambda _: self.override_materials(self.subject_scene, self.subject_material))
        self.subject_scene.setSource(QUrl.fromLocalFile(str('tag_aligner/assets/JAN.gltf')))

        self.subject_transform = Qt3DCore.QTransform()
        self.subject_entity.addComponent(self.subject_scene)
        self.subject_entity.addComponent(self.subject_transform)

        self.light_entity = Qt3DCore.QEntity(self.subject_entity)
        self.light = Qt3DRender.QPointLight(self.light_entity)
        self.light.setIntensity(0.5)
        self.light.setLinearAttenuation(0.0)
        self.light_transform = Qt3DCore.QTransform()
        self.light_transform.setTranslation(QVector3D(0, 0.1, 0.1))
        self.light_entity.addComponent(self.light)
        self.light_entity.addComponent(self.light_transform)


        self.gaze_pointer_entity = Qt3DCore.QEntity(self.subject_entity)
        self.gaze_ray_mesh = Qt3DRender.QSceneLoader()
        self.gaze_ray_mesh.statusChanged.connect(lambda _: self.override_materials(self.gaze_ray_mesh, self.ray_material))
        self.gaze_ray_mesh.setSource(QUrl.fromLocalFile(str('tag_aligner/assets/ray.gltf')))
        self.gaze_pointer_transform = Qt3DCore.QTransform()
        self.gaze_pointer_entity.addComponent(self.gaze_ray_mesh)
        self.gaze_pointer_entity.addComponent(self.gaze_pointer_transform)

        self.setRootEntity(self.root_entity)

        self.camera_controller = Qt3DExtras.QOrbitCameraController(self.root_entity)
        self.camera_controller.setLinearSpeed(50.0)
        self.camera_controller.setLookSpeed(180.0)
        self.camera_controller.setCamera(self.camera())

        self.initial_pose_set = False

    def override_materials(self, scene_tree, mat):
        for entity_name in scene_tree.entityNames():
            scene_tree.entity(entity_name).addComponent(mat)

    def resizeEvent(self, event):
        self.camera().setAspectRatio(self.width() / self.height())

    def set_subject_pose(self, position, rotation):
        if not self.initial_pose_set:
            self.camera().setPosition(QVector3D(3, 3, 3))
            self.camera().setViewCenter(position)

            self.initial_pose_set = True
        self.subject_transform.setTranslation(position)
        self.subject_transform.setRotation(rotation)

    def set_gaze_angle(self, rotation):
        self.gaze_pointer_entity.setEnabled(rotation is not None)
        if rotation is not None:
            self.gaze_pointer_transform.setRotation(rotation)


class SceneViewerWidget(QWidget):
    def __init__(self):
        super().__init__()

        self.scene_viewer = SceneViewerWindow()
        self.container_widget = self.createWindowContainer(self.scene_viewer)
        self.container_widget.setParent(self)

        self.setMinimumSize(200, 200)
        self.poses = []

    def resizeEvent(self, event):
        self.container_widget.resize(self.size())

    def load_scene(self, path):
        self.scene_viewer.scene.setSource(QUrl.fromLocalFile(str(path)))

    def set_subject_pose(self, position, rotation):
        self.scene_viewer.set_subject_pose(position, rotation)

    def set_gaze_angle(self, rotation):
        self.scene_viewer.set_gaze_angle(rotation)


class ScenePlayerWidget(SceneViewerWidget):
    def __init__(self):
        super().__init__()

        self.poses = []
        self.gazes = []
        self.installEventFilter(self)

    def load_poses(self, path):
        with path.open('r') as csv_file:
            reader = csv.DictReader(csv_file)
            self.poses = []
            for row in reader:
                row = {k:float(v) for k,v in row.items()}
                self.poses.append(row)

        print(len(self.poses), 'poses loaded')

    def set_gazes(self, gazes):
        self.gazes = gazes

    def seek_to_time(self, timestamp_ms):
        pose_idx = find_pose_index_by_timestamp(self.poses, timestamp_ms/1000.0)
        if pose_idx is not None:
            pose = self.poses[pose_idx]

            cam_pose_cv = Transformation(
                np.array([pose['translation_x'], pose['translation_y'], pose['translation_z']]),
                Rotation.from_quat([pose['rotation_x'], pose['rotation_y'], pose['rotation_z'], pose['rotation_w']]),
            )
            cam_pose_qt = cv_space_to_qt3d_space(cam_pose_cv)

            position = QVector3D(*cam_pose_qt.position)
            x,y,z,w = cam_pose_qt.rotation.as_quat()
            rotation = QQuaternion(w,x,y,z)

            self.scene_viewer.set_subject_pose(position, rotation)

        gaze_idx = find_gaze_index_by_timestamp(self.gazes, timestamp_ms/1000.0)
        if gaze_idx is not None:
            gaze = self.gazes[gaze_idx]
            gaze_transform_cv = Transformation(
                np.array([0.0, 0.0, 0.0]),
                Rotation.from_euler('xyz', [gaze['elevation [deg]'], gaze['azimuth [deg]'], 0.0], degrees=True),
            )
            gaze_pose_qt = cv_space_to_qt3d_space(gaze_transform_cv)
            x,y,z,w = gaze_pose_qt.rotation.as_quat()
            rotation = QQuaternion(w,x,y,z)
            self.scene_viewer.set_gaze_angle(rotation)
        else:
            self.scene_viewer.set_gaze_angle(None)

    def move(self, x, y, z):
        self.scene_viewer.camera().translateWorld(QVector3D(x, y, z))


def find_gaze_index_by_timestamp(gazes, timestamp, omission_threshold=1/100):
    left_idx = 0
    right_idx = len(gazes)-1
    while right_idx - left_idx > 1:
        mid_idx = (left_idx + right_idx) // 2

        if timestamp < gazes[mid_idx]['timestamp']:
            right_idx = mid_idx
        elif timestamp > gazes[mid_idx]['timestamp']:
            left_idx = mid_idx
        else:
            break

    if abs(timestamp-gazes[mid_idx]['timestamp']) > omission_threshold:
        return None

    return mid_idx

def find_pose_index_by_timestamp(poses, timestamp, omission_threshold=1/15):
    left_idx = 0
    right_idx = len(poses)-1
    while right_idx - left_idx > 1:
        mid_idx = (left_idx + right_idx) // 2

        if timestamp < poses[mid_idx]['start_timestamp']:
            right_idx = mid_idx
        elif timestamp > poses[mid_idx]['end_timestamp']:
            left_idx = mid_idx
        else:
            break

    mean_ts = (poses[mid_idx]['start_timestamp']+poses[mid_idx]['end_timestamp'])/2
    if abs(timestamp-mean_ts) > omission_threshold:
        return None

    return mid_idx



if __name__ == '__main__':
    app = PlaybackApp()
    app.load_recording(Path(sys.argv[1]))
    app.load_scene(Path(sys.argv[2]))
    app.play()
    app.exec()
