# Tag Aligner

This tool takes camera pose data from a Pupil Labs RIM enrichment from it's arbitrary coordinate space and scale and transforms those poses to a known space and scale using one or more AprilTag markers.

## Depedendencies
```bash
pip install -r requirements.txt
```

## Usage

### 0. Preparation

1. Create a [RIM enrichment](https://docs.pupil-labs.com/neon/pupil-cloud/enrichments/reference-image-mapper/) just like an other.
    * At least one of the recordings needs to contain an AprilTag marker with a known size, position, and orientation. This can be the scanning recording, but does not need to be.
    * Multiple tags may improve the accuracy.
2. Download the enrichment data using the Pupil Cloud API.
    ```bash
    python -m downloader.rim api_key workspace_id project_id enrichment_id recording_id
    ```

3. Prepare a `json` file with reference tag information
    * Units for position and size are in output space units
    * Rotation is a quaternion in `[x, y, z, w]` order
    * The coordinate system must match OpenCV's. See [notes](#notes) below.
    * Here's an example that contains size and pose information for two different AprilTag markers:
        ```json
        [
            {
                "id": 492,
                "size": 0.1730375,
                "position": [0, -1.1755, -0.102172],
                "rotation": [0.0, 0.0, 0.707107, 0.707107]
            },
            {
                "id": 493,
                "size": 0.1730375,
                "position": [0.25, -1.1755, -0.102172],
                "rotation": [0.0, 0.0, 0.707107, 0.707107]
            },
        ]
        ```


### 1. Calculate the transformation

Run the `tag_aligner.calculate_alignment` module to create an alignment file by specifying the folder location of the recording which contains the AprilTag marker(s), the path to the `reference_tags.json` file, and the output file path.
```bash
python -m tag_aligner.calculate_alignment path/to/tag/recording_folder/ path/to/reference_tags.json path/to/output/alignment.json
```

### 2. Apply the transformation

Run the `tag_aligner.apply_alignment` module to transform recording poses by specifying the recording folder you wish to transform and the alignment file.
```bash
python -m tag_aligner.apply_alignment path/to/recording_folder/ path/to/alignment.json
```

This will create a new file in the recording folder named `aligned_poses.csv` with the scaled and aligned poses. Note that orientation is specified as a quaternion.

### 3. Bonus: Visualize
This requires an additional dependency not specified in `requirements.txt`:
```bash
pip install pyside6
```

Run the `tag_aligner.playback` module to view the recording side-by-side with a digital twin by specifying the path to the recording and a `gltf` scene file.
```bash
python -m tag_aligner.playback path/to/recording_folder/ path/to/digital/scene.gltf
```

To control the camera in the digital twin view, you must click on the view to give it focus. The controls are as follows:
| Input              | Action                   |
|--------------------|--------------------------|
| Left mouse button  | While the left mouse button is pressed, mouse movement along x-axis moves the camera left and right and movement along y-axis moves it up and down.
| Right mouse button | While the right mouse button is pressed, mouse movement along x-axis pans the camera around the camera view center and movement along y-axis tilts it around the camera view center.
| Left+Right buttons | While both the left and the right mouse button are pressed, mouse movement along y-axis zooms the camera in and out without changing the view center.
| Scroll wheel       | Zooms the camera in and out without changing the view center.
| Arrow keys         | Move the camera vertically and horizontally relative to camera viewport.
| Page up/down       | Move the camera forwards and backwards.
| Alt                | Changes the behovior of the arrow keys to pan and tilt the camera around the view center. Disables the page up and page down keys.


## Notes

The output space coordinate system matches OpenCV's:
* Positive X extends rightwards from the camera view
* Positive Y extends downwards from the camera view
* Positive Z extends forward from the camera view

To convert Blender-space poses to OpenCV (e.g., in the reference tag json file):
| OpenCV           | Blender          |
| ---------------- | ---------------- |
| Position x       | Position x       |
| Position **y**   | Position **-z**  |
| Position **z**   | Position **y**   |
| Quaternion x     | Quaternion x     |
| Quaternion **y** | Quaternion **z** |
| Quaternion **z** | Quaternion **y** |
| Quaternion w     | Quaternion w     |
