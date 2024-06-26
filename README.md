# Tag Aligner

This tool takes camera pose data from a Pupil Labs RIM enrichment from it's arbitrary coordinate space and scale and transforms those poses to a known space and scale using one or more AprilTag markers.

## Depedendencies
```bash
pip install -r requirements.txt
```

## Usage

### 0. Preparation

1. Create a [RIM enrichment](https://docs.pupil-labs.com/neon/pupil-cloud/enrichments/reference-image-mapper/) just like any other.
    * At least one of the recordings needs to contain an AprilTag marker with a known size, position, and orientation. This can be the scanning recording, but does not need to be.
    * Multiple tags may improve the accuracy.
2. Download the enrichment data using the Pupil Cloud API.
    ```bash
    python -m downloader.rim api_key workspace_id project_id enrichment_id recording_id
    ```

    The IDs are found as follows:
     * The Recording ID is found by right-clicking on a recording and choosing “View recording information” in the menu that appears.
     * The Enrichment ID is found by opening the Enrichment and clicking the three button menu above and to the right of “Enrichment Type - Reference Image Mapper”. Choose “Copy enrichment ID” in the menu that appears.
     * When the tab with Pupil Cloud is open to the Project overview, then the Workspace ID and Project ID are found in the URL address bar of your browser. In the example URL below, they are marked in bold:

        <pre>https://cloud.pupil-labs.com/workspaces/<b>83f092d1-9380-46f9-b639-432d61de0170</b>/projects/<b>6f12dbd1-810e-48ca-9161-8c171bd246e0</b>/recordings</pre>

3. Prepare a `json` file with reference tag information
    * The "id" is the ID number of an AprilTag from the tag36h11 family.
    * Units for position and size are in output space units
    * Size is the length for one side of the black part of an AprilTag, excluding the white border.
    * Position is measured from the center of the tag
    * Rotation is a quaternion in `[x, y, z, w]` order
    * An upright tag positioned on a wall would have a quaternion value of `[0.0, 0.0, 0.0, 1.0]`.
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

For example, if the position is [-0.97, 1.37, 1.26] in Blender, then it is [-0.97, -1.26, 1.37] in OpenCV format.

Note that Blender's default initial orientation for a Plane is rotated -90 degrees about the x-axis relative to OpenCV's assumptions.
In other words, for the purposes of digital twin development, Blender's "zero rotation" for a Plane is "flat on the floor", while
OpenCV's is "vertical on the wall".