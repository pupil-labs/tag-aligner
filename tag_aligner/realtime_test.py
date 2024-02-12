from PySide6.QtCore import *
from PySide6.QtWidgets import *
from PySide6.QtGui import *

import math
import cv2
import numpy as np

from pupil_apriltags import Detector
from scipy.spatial.transform import Rotation

from pupil_labs.realtime_api.simple import discover_one_device

from .playback import SceneViewerWidget
from .scaled_image_view import ScaledImageView, qimage_from_frame

from .maths import (
    cv_space_to_qt3d_space,
    rodrigues_to_rotation,
    Transformation
)


class Webcam:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.camera_matrix = np.array([
            [1000, 0.0, 1920/2.0],
            [0.0, 1000, 1080/2.0],
            [0.0, 0.0, 1.0],
        ])

        self.camera_distortion = np.array([[ 0.0, 0.0, 0.0, 0.0, 0.0 ]])

    def get_frame(self):
        status, frame = self.cap.read()
        return frame

    def close(self):
        self.cap.release()


class Neon:
    def __init__(self):
        print('Attempting device discovery...')
        self.device = discover_one_device()
        print('Connected!')

        calibration = self.device.get_calibration()
        self.camera_matrix = calibration["scene_camera_matrix"][0]
        self.camera_distortion = calibration["scene_distortion_coefficients"][0]

    def get_frame(self):
        data = self.device.receive_scene_video_frame(timeout_seconds=0)
        if data is not None:
            return data.bgr_pixels

        return None

    def close(self):
        self.device.close()


class RealtimeWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.video_widget = ScaledImageView()
        self.scene_widget = SceneViewerWidget()
        self.debug_info_widget = QLabel("One moment...")
        self.debug_info_widget.setStyleSheet("font-family: monospace; font-size: 14pt")

        self.setLayout(QGridLayout())
        self.layout().addWidget(self.video_widget, 0, 0)
        self.layout().addWidget(self.scene_widget, 0, 1)
        self.layout().addWidget(self.debug_info_widget, 1, 0, 1, 2)
        self.layout().setRowStretch(0, 1)

        self.scene_widget.load_scene("recordings/tag-only/paper.gltf")
        self.resize(800, 400)



class App(QApplication):
    def __init__(self):
        super().__init__()
        self.display = RealtimeWindow()

        self.poll_timer = QTimer()
        self.poll_timer.setInterval(1000//60)
        self.poll_timer.timeout.connect(self._poll)

        self.camera = None
        self.tag_detector = Detector()

        self.root_tag_id = 492
        self.root_tag_size = 0.1730375 # meters

        self.tag_points_3d = np.array([
            [-self.root_tag_size/2,  self.root_tag_size/2, 0], # BL
            [ self.root_tag_size/2,  self.root_tag_size/2, 0], # BR
            [ self.root_tag_size/2, -self.root_tag_size/2, 0], # TL
            [-self.root_tag_size/2, -self.root_tag_size/2, 0], # TR
        ])

        self.tag_truth = Transformation(
            np.array([0.0, 0.0, 0.0]),
            Rotation.from_quat([-0.707, 0.0, 0.0, 0.707]) # flat on the ground or desk
        )


    def _poll(self):
        frame = self.camera.get_frame()
        if frame is None:
            return

        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        tags = self.tag_detector.detect(frame_gray)
        for detected_tag in tags:
            if detected_tag.tag_id != self.root_tag_id:
                continue

            tag_corners = detected_tag.corners

            ok, (tag_rotation,_), (tag_position,_), (error,_) = cv2.solvePnPGeneric(
                self.tag_points_3d,
                tag_corners,
                self.camera.camera_matrix,
                self.camera.camera_distortion,
                flags = cv2.SOLVEPNP_IPPE_SQUARE
            )

            if not ok:
                continue

            tag_pose = Transformation(tag_position, rodrigues_to_rotation(tag_rotation))
            cam_pose = Transformation().relative_to(tag_pose)

            correction = calc_correction(tag_pose, self.tag_truth)
            cam_pose = Transformation().apply(correction)

            cam_pose2 = cv_space_to_qt3d_space(cam_pose)

            text = "Tag\n" + pose_to_string(tag_pose)
            text += "\nCamera\n" + pose_to_string(cam_pose)
            text += "\nPlayback cam\n" + pose_to_string(cam_pose2)

            position = QVector3D(*cam_pose2.position)
            x,y,z,w = cam_pose2.rotation.as_quat()
            rotation = QQuaternion(w,x,y,z)

            self.display.scene_widget.set_subject_pose(position, rotation)

            colors = [
                (0, 255, 0),
                (255, 255, 255,),
                (0, 0, 0,),
                (0, 0, 255,),
            ]
            for corner_idx,corner in enumerate(tag_corners.astype(int)):
                frame = cv2.circle(frame, corner, 5, colors[corner_idx], 5)

            self.display.debug_info_widget.setText(text)

        # Display the resulting frame
        self.display.video_widget.set_image(qimage_from_frame(frame))

    def _start(self):
        self.camera = Neon()
        self.poll_timer.start()

    def exec(self):
        QTimer.singleShot(100, self._start)
        self.display.showMaximized()

        super().exec()

        self.camera.close()


def calc_correction(bad, good):
    good_inv = np.linalg.inv(good.to_matrix())
    return bad.to_matrix() @ good_inv

def apply_correction(transform, correction_matrix):
    return Transformation.from_matrix(np.linalg.inv(correction_matrix) @ transform.to_matrix())

def putText(image, text, position=(10, 30)):
    for line_idx,text in enumerate(text.split('\n')):
        thicks = [ 4, 1 ]
        colors = [ (64, 64, 64), (255, 255, 255) ]

        # Using cv2.putText() method
        for (thick,color) in zip(thicks, colors):
            image = cv2.putText(
                image, text,
                (position[0], position[1] + line_idx*30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                color,
                thick,
                cv2.LINE_AA
            )

    return image

def pose_to_string(pose):
    euler = pose.rotation.as_euler('yxz')
    degs = [v / math.tau * 360 for v in euler]
    quat = pose.rotation.as_quat()
    pos_str = '[' + ', '.join([f'{v:0.3f}' for v in pose.position]) + ']'
    rot_str = '[' + ', '.join([f'{round(v)}' for v in degs]) + ']'
    quat_str = '[' + ', '.join([f'{v:0.3f}' for v in quat]) + ']'

    return f"    {pos_str}\n    {rot_str}\n    {quat_str}"


app = App()
app.exec()