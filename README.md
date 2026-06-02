# meletis-lab-to-nwb

NWB conversion scripts for Meletis lab data to the
[Neurodata Without Borders](https://nwb-overview.readthedocs.io/) data format.


## Installation

We recommend installing the package directly from Github. This option has the advantage that the source code can be modified if you need to amend some of the code we originally provided to adapt to future experimental differences. To install the conversion from GitHub you will need to use `git` ([installation instructions](https://github.com/git-guides/install-git)). We also recommend the installation of `conda` ([installation instructions](https://docs.conda.io/en/latest/miniconda.html)) as it contains all the required machinery in a single and simple install.

From a terminal (note that conda should install one in your system) you can do the following:

```bash
git clone https://github.com/catalystneuro/meletis-lab-to-nwb
cd meletis-lab-to-nwb
conda env create --file make_env.yml
conda activate meletis_lab_to_nwb_env
```
This creates a [conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/concepts/environments.html) which isolates the conversion code from your system libraries. We recommend that you run all your conversion related tasks and analysis from the created environment in order to minimize issues related to package dependencies.

Alternatively, if you want to avoid conda altogether (for example if you use another virtual environment tool) you can install the repository with the following commands using only pip:
```bash
git clone https://github.com/catalystneuro/meletis-lab-to-nwb
cd meletis-lab-to-nwb
pip install --editable .
```

Note:
both of the methods above install the repository in [editable mode](https://pip.pypa.io/en/stable/cli/pip_install/#editable-installs).
The dependencies for this environment are stored in the dependencies section of the `pyproject.toml` file.

All conversion scripts can be run from the single `meletis_lab_to_nwb_env` environment.

---

## Repository Structure

```
meletis-lab-to-nwb/
├── make_env.yml
├── pyproject.toml
├── README.md
└── src/meletis_lab_to_nwb/
    ├── interfaces/               # Shared interfaces (FiberPhotometryInterface, ReachingBehaviorInterface)
    ├── arrow_maze_choice_task/   # T-maze decision task
    ├── open_field_test/          # Open arena + VAME + fiber photometry
    ├── opto_dlight/              # Optogenetic self-stimulation + dLight
    ├── reaching_test/            # Forelimb reaching motor task
    ├── water_consumption/        # Reaching-for-water + fiber photometry
    ├── video/                    # AVI → MP4 utility
    └── tutorials/                # Demo notebooks
```

Each conversion directory contains:

- `convert_session.py` — converts one session to NWB
- `convert_all_sessions.py` — batch conversion with `ProcessPoolExecutor`
- `nwbconverter.py` — `NWBConverter` subclass assembling all interfaces
- `metadata.yaml` — NWB metadata template (deep-merged at conversion time)
- `conversion_notes.md` — file format details, decisions, and open questions

## Conversions

- [Arrow Maze Choice Task](#arrow-maze-choice-task)
- [Open Field Test](#open-field-test)
- [Opto + dLight](#opto--dlight)
- [Reaching Test](#reaching-test)
- [Water Consumption](#water-consumption)

---

### Arrow Maze Choice Task

**Directory:** [`src/meletis_lab_to_nwb/arrow_maze_choice_task/`](src/meletis_lab_to_nwb/arrow_maze_choice_task/)

T-maze decision task in which mice choose between two arms. Sessions are indexed via
`details.csv` and each session maps to one video and one DeepLabCut pose estimation file.

| Data stream | Format | NeuroConv interface |
|-------------|--------|---------------------|
| Behavior video | H.264 MP4, 856×818, 30 fps | `ExternalVideoInterface` |
| Pose estimation | DeepLabCut CSV (8 keypoints) | `DeepLabCutInterface` |

#### Running the conversion

```bash
python src/meletis_lab_to_nwb/arrow_maze_choice_task/convert_session.py   # single session
python src/meletis_lab_to_nwb/arrow_maze_choice_task/convert_all_sessions.py  # batch
```

---

### Open Field Test

**Directory:** [`src/meletis_lab_to_nwb/open_field_test/`](src/meletis_lab_to_nwb/open_field_test/)

Open field combining video tracking, pose estimation, unsupervised
behavioral segmentation (VAME), and fiber photometry. Multiple cohorts are supported
(`dLight_dStr`, `dLight_vStr`, `fp_dat`, `fp_anxa1`, `dat-cre`, `anxa1-flp`) with
per-group fiber photometry metadata (brain region, indicator, optical fiber).

| Data stream | Format | NeuroConv interface |
|-------------|--------|---------------------|
| Behavior video | H.264 MP4, 30 fps | `ExternalVideoInterface` |
| Pose estimation | DeepLabCut CSV | `DeepLabCutInterface` |
| Behavioral segmentation | VAME motif labels + latent vectors (`.npy`) | `VameInterface` (custom) |
| Fiber photometry (raw) | CSV (`time`, `ref` 405 nm, `sig` 470 nm) | `FiberPhotometryInterface` (custom) |
| Fiber photometry (dF/F) | CSV (processed, motion-corrected) | `FiberPhotometryInterface` (custom) |
| Behavioral events | CSV (custom) | `OpenFieldTestBehaviorInterface` (custom) |

#### Running the conversion

```bash
python src/meletis_lab_to_nwb/open_field_test/convert_session.py
python src/meletis_lab_to_nwb/open_field_test/convert_all_sessions.py
```

---

### Opto + dLight

**Directory:** [`src/meletis_lab_to_nwb/opto_dlight/`](src/meletis_lab_to_nwb/opto_dlight/)

Optogenetic self-stimulation paradigm (ChRmine, 640 nm, 40 Hz, bilateral SNc) with
simultaneous dLight1.3b fiber photometry in striatum. Mice nosepoke to trigger laser
bursts; five intensities tested per animal. Corresponds to Extended Data Fig. 7F–J.

| Data stream | Format | NeuroConv interface |
|-------------|--------|---------------------|
| Optogenetic TTL | CSV (timestamp, frame, boolean state) | `OptogeneticsTTLInterface` (custom) |
| Fiber photometry (raw) | CSV (`time`, `ref`, `sig`) | `FiberPhotometryInterface` (custom) |
| Fiber photometry (dF/F) | CSV (processed) | `FiberPhotometryInterface` (custom) |

#### Running the conversion

```bash
python src/meletis_lab_to_nwb/opto_dlight/convert_session.py
python src/meletis_lab_to_nwb/opto_dlight/convert_all_sessions.py
```

---

### Reaching Test

**Directory:** [`src/meletis_lab_to_nwb/reaching_test/`](src/meletis_lab_to_nwb/reaching_test/)

Forelimb reaching-for-water motor task used to characterize the role of Anxa1+ SNc
dopamine neurons in motor skill. Two experimental arms: chronic silencing via tetanus
toxin (tet vs ctrl cohorts) and acute optogenetic silencing via Archaerhodopsin
(arch_anxa1 vs arch_ctrl). Corresponds to Fig. 7E–N and Supplementary Fig. 15.

Source videos are `.avi` (MPEG-4 Part 2, 60 fps, FLIR camera) and must be converted
to MP4 before NWB conversion — see [Video Conversion](#video-conversion-avi--mp4).

| Data stream | Format | NeuroConv interface |
|-------------|--------|---------------------|
| Behavior video | AVI → MP4 (H.264, 60 fps) | `ExternalVideoInterface` |
| Pose estimation | DeepLabCut CSV | `DeepLabCutInterface` |
| Reach annotations | CSV (frame-indexed, paw + outcome) | `ReachingBehaviorInterface` (custom) |

#### Running the conversion

```bash
python src/meletis_lab_to_nwb/reaching_test/convert_session.py
python src/meletis_lab_to_nwb/reaching_test/convert_all_sessions.py
```
---

### Water Consumption

**Directory:** [`src/meletis_lab_to_nwb/water_consumption/`](src/meletis_lab_to_nwb/water_consumption/)

Four-day forelimb reaching-for-water training task with simultaneous fiber photometry.
Cohorts include dLight1.3b (dCP and cCP sites) and jGCaMP8m (pan-DA DAT-Cre and
Anxa1-specific Anxa1-Flp lines). Per-group metadata selects the correct brain region,
indicator label, and optical fiber configuration automatically.

Source videos are `.avi` and must be converted to MP4 before NWB conversion — see
[Video Conversion](#video-conversion-avi--mp4).

| Data stream | Format | NeuroConv interface |
|-------------|--------|---------------------|
| Behavior video | AVI → MP4 (H.264, 60 fps) | `ExternalVideoInterface` |
| Fiber photometry (raw) | CSV (`time`, `ref` 405 nm, `sig` 470 nm, ~60 Hz) | `FiberPhotometryInterface` (custom) |
| Fiber photometry (dF/F) | CSV (motion-corrected dF/F) | `FiberPhotometryInterface` (custom) |
| Reach annotations | CSV (frame-indexed, paw + outcome) | `ReachingBehaviorInterface` (custom) |

#### Running the conversion

```bash
python src/meletis_lab_to_nwb/water_consumption/convert_session.py
python src/meletis_lab_to_nwb/water_consumption/convert_all_sessions.py
```

---

## Key Dependencies

- [`neuroconv`](https://neuroconv.readthedocs.io/) — core conversion framework
- [`nwbinspector`](https://nwbinspector.readthedocs.io/) — NWB file validation
- `ffmpeg` — video transcoding (system install, not a Python package)
