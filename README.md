# Camera Axis Auto Reslice

Camera Axis Auto Reslice is a 3D Slicer scripted module for interactive oblique MRI reslicing from a cortical surface view.

The module uses the selected 3D view camera direction as the slice axis. After initialization, rotating the 3D view automatically updates the oblique slice view, while preserving the current slice depth. This is intended for workflows where a FreeSurfer pial/white cortical surface and a registered MRI volume are already aligned in Slicer.

## What It Does

- Select an MRI volume as the source image.
- Optionally select a cortical surface model, such as a FreeSurfer pial surface imported as a Slicer model.
- Use the current 3D view center ray to initialize the slicing anchor point.
- Drive a Slicer slice view using the current 3D camera viewing direction.
- Automatically update the slice orientation as the 3D view rotates.
- Preserve current depth when the camera rotates, so the same region can be inspected from multiple viewing angles.
- Display an optional 3D plane and axis line for spatial context.

## Requirements

- 3D Slicer 5.x recommended.
- MRI data loaded as a scalar volume.
- Optional cortical surface loaded as a model node.

The module assumes registration/alignment between the MRI volume and cortical surface has already been solved upstream.

## Installation

### Developer installation

1. Clone this repository:

   ```bash
   git clone https://github.com/your-github-username/CameraAxisAutoReslice.git
   ```

2. Open 3D Slicer.
3. Go to `Edit -> Application Settings -> Modules`.
4. Add this folder to `Additional module paths`:

   ```text
   /path/to/CameraAxisAutoReslice/CameraAxisAutoReslice
   ```

5. Restart Slicer.
6. Search for `Camera Axis Auto Reslice` in the module selector.

## Usage

1. Load the MRI volume in Slicer.
2. Load the cortical surface model if available.
3. Open `Camera Axis Auto Reslice`.
4. Set:
   - `MRI volume`: the source MRI volume.
   - `Surface model`: optional cortical surface model.
   - `3D view`: the 3D view used to inspect the pial surface.
   - `Slice view`: the slice view to drive, such as Red.
5. Rotate and pan the 3D view so the target region is centered.
6. Click `Start slicing`.
7. Rotate the 3D view. The oblique slice updates automatically.
8. Use `Axis offset` to move forward/backward along the current camera axis.
9. Use `Re-anchor point` to choose a new anchor from the current view center.
10. Use `Flip axis` if the positive offset direction is opposite to the desired direction.

## Controls

### MRI volume

The scalar volume used for reslicing.

### Surface model

Optional model used to compute the initial anchor point. If selected, the module casts a ray from the current camera through the 3D view center and anchors the slice at the first surface intersection. If no intersection is found, it falls back to the closest surface point to the camera focal point.

### 3D view

The source camera view. The current camera direction defines the slice axis.

### Slice view

The Slicer slice view controlled by the module.

### Axis offset

Moves the slice plane along the current camera axis. The value is preserved while rotating the 3D camera.

### Flip axis

Reverses the depth axis used for offset motion.

### Auto update

When enabled, camera rotation automatically updates the slice orientation.

### Show plane

Shows or hides the 3D plane and axis line.

### Start slicing

Initializes the anchor point from the current 3D view center and starts camera-driven slicing.

### Re-anchor point

Recomputes the anchor point from the current 3D view center.

## Data Notes

The surface must be a Slicer model node. DICOM, NIfTI, labelmap, and segmentation nodes are not valid surface models unless converted/exported to model format first.

Typical FreeSurfer-derived surfaces include:

- `lh.pial`
- `rh.pial`
- `lh.white`
- `rh.white`

If Slicer does not import the surface directly as a model, convert it to a Slicer-supported mesh format such as `.vtk`, `.vtp`, `.ply`, `.stl`, or `.obj`.

## Limitations

- This module does not run FreeSurfer reconstruction.
- This module does not perform MRI-surface registration.
- This module does not export DICOM.
- Slice quality depends on the source MRI voxel spacing and anisotropy.
- The module is designed for interactive preview and planning, not validated clinical use.

## Repository Layout

```text
CameraAxisAutoReslice/
  CMakeLists.txt
  CameraAxisAutoReslice.py
CMakeLists.txt
README.md
.gitignore
```

## License

No license has been selected yet. Add a license before publishing if you want other users to have explicit reuse rights.

