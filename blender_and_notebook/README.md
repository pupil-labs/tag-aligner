This folder contains an Add-on to import Tag Aligner data into Blender, as well as a Python (Jupyter) notebook that shows you how to plot an overhead projection of the data.

The Blender Add-on can be installed as follows:

- Download the 'tag_aligner_blender_addon.zip' file found in [Releases](https://github.com/pupil-labs/tag-aligner/releases).

- Open Blender and install the Add-on by going to Edit -> Preferences -> Add-ons -> Install and then choose the 'tag_aligner_blender.zip' file (no need to extract it).

- Import a 3D scene that you have prepared for your recording.

- Open the [Sidebar in Blender](https://www.youtube.com/watch?v=TrS18jCazok) and click on the Tag Aligner tab.

- Put the path of your recording directory in the "rec_dir" text box. Note that the recording should have already been processed with Tag Aligner.

- Next press the "Import eyetracker meshes" button to import the objects needed for animation. You should only need to press this button once per scene.

- You can now choose how many frames from your recording you want to animate. The number of frames are specified with respect to Neon's scene camera that runs at 30 frames per second. For an initial test, choosing frames 1 to 200 (approximately the first 6.7 seconds of a recording) can help to determine if you have everything set up correctly.

- Choose whether you want gaze to be mapped with a basic raycast intersection routine or a "gaze cone" intersection routine. Leaving the box unchecked will be slightly faster.

- Now, press the "Apply Tag Aligner data" button. Depending on the number of frames that you are animating, it could take some time for all data to be imported and applied.

Once the process finishes, open the Animation view and press the spacebar to see the recording play in 3D!

You can also open the 'tag_aligner_blender_addon.py' file to see the code of the Add-on, and the assets can be opened in Blender for further inspection.
