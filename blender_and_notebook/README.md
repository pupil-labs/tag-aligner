This folder contains an Add-on to import Tag Aligner data into Blender, as well as a Python (Jupyter) notebook that shows how to plot an overhead projection of the data.

The Python notebook uses data from the recording in the accompanying Alpha Labs article. It has already been enriched and processed with Tag Aligner. [Download it](https://drive.google.com/file/d/14pkL5x3wKxACO5hzC0Vi_l2F2Xmmekcr/view?usp=sharing) if you want to give the notebook a try (update file paths in the notebook, if necessary).

The Blender Add-on can be installed as follows:

- Download the 'tag_aligner_blender_addon.zip' file (you already have it if you cloned this repository)

- Download a recording that has already been enriched and processed by Tag Aligner, such as [this recording](https://drive.google.com/file/d/14pkL5x3wKxACO5hzC0Vi_l2F2Xmmekcr/view?usp=sharing) that was used to make the accompanying Alpha Labs article.

- Open Blender and install the Add-on by going to Edit -> Preferences -> Add-ons -> Install and then choose the tag_aligner_blender.zip file (no need to extract it)

- Import a 3D scene that you have prepared for your recording. We [provide a glTF export (in glb format)](https://drive.google.com/file/d/14qmMqKKY_JZfUwOfjuvjiSUaKX0zPWgx/view?usp=sharing) of our scene used for the Tag Aligner Alpha Labs article. Use that if you are also using the Neon recording that was linked above.

- Open the [Sidebar in Blender](https://www.youtube.com/watch?v=TrS18jCazok) and click on the Tag Aligner tab.

- Put the path of your recording directory in the "rec_dir" text box.

- Next press the "Import eyetracker meshes" button to import the objects needed for animation. You should only need to press this button once per scene.

- You can now choose how many frames from your recording you want to animate. The number of frames are specified with respect to Neon's scene camera that runs at 30 frames per second. For an initial test, choosing frames 1 to 200 (approximately the first 6.7 seconds of a recording) can help to determine if you have everything set up correctly.

- Choose whether you want gaze to be mapped with a basic raycast intersection routine or a "gaze cone" intersection routine. Leaving the box unchecked will be faster.

- Now, press the "Apply Tag Aligner data" button. Depending on the number of rames that you are animating, it could take some time for all data to be imported and applied.

Once the process finishes, open the Animation view and press spacebar to see the recording play in 3D!

You can also open the 'tag_aligner_blender_addon.py' file to see the code of the Add-on, and the assets can be opened in Blender for further inspection.