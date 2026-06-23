# Notes concerning the open_field_test conversion

## Data Location
`/Volumes/T9/data/Meletis/oft/`

## File Structure
```
oft/
├── details.csv                              # Session metadata (161 rows)
├── videos/
│   ├── oft_2023-05-16T15_31_06.mp4          # 161 MP4 files (74 oft_ + 87 tmaze_ prefix)
│   └── ...
├── pose_estimation/
│   ├── oft_2023-05-16T15_31_06.csv          # 161 DLC CSV files (1:1 with videos)
│   └── ...
├── NEW_vame/
│   ├── config.yaml                                          # Shared VAME project config
│   ├── 42_km_label_oft_2023-05-16T15_31_06.npy             # VAME motif label files (161)
│   ├── latent_vector_oft_2023-05-16T15_31_06.npy           # VAME latent vector files (161)
│   ├── oft_2023-05-16T15_31_06_aligned.csv                 # Aligned analysis files (161)
│   └── ...
├── signal_df/
│   ├── oft_2023-11-28T14_52_48_signal_df.csv  # 31 processed dF/F signal files
│   └── ...
└── signal/
    ├── oft_2023-11-28T14_52_48_signal.csv     # 31 raw fiber photometry acquisition files
    └── ...
```

## Data Streams

### Video
- Format: H.264 MP4, 30 fps
- View: from below (transparent floor)
- Arena: 40x40 cm
- NeuroConv interface: `ExternalVideoInterface`

### Pose Estimation (DeepLabCut)
- Format: CSV with standard DLC multi-header
- 6 keypoints: snout, leftFrontPaw, rightFrontPaw, leftBackPaw, rightBackPaw, tailBase
- NeuroConv interface: `DeepLabCutInterface`

### VAME Motifs
- Format: .npy (1D int array of motif labels)
- Single model: 42-motif (`NEW_vame/`, prefix `42_km_label_`)
- Replaces previous two-model approach (`vame_157`/`vame_36` with `47_km_label_` prefix)
- Rate: 30 Hz (one label per video frame)
- Config shared across sessions: `NEW_vame/config.yaml`
- NeuroConv interface: `neuroconv.datainterfaces.VameInterface` (built-in since `add-vame-interface` branch)
- Requires ndx-vame == 0.3.1
- NWB storage: `processing/behavior/VAME_42` (`VAMEProject` container)
  - `motif_series["MotifSeries"]` — 1D int32, HMM algorithm (from `config["parameterization"]`)
  - `VAMEProject.time_window_samples` = 30 (from `config["time_window"]`)
  - Access: `nwbfile.processing["behavior"]["VAME_42"].motif_series["MotifSeries"]`

### VAME Latent Vectors
- Format: .npy (2D float32 array, frames × latent dims)
- Files: `NEW_vame/latent_vector_{video_name}.npy`
- Written alongside motif labels by the same `VameInterface` as `LatentSpaceSeries`

### Fiber Photometry Signal
- Processed dF/F: `signal_df/{video_name}_signal_df.csv` — isosbestic-corrected dF/F, ~60 Hz
- Raw acquisition: `signal/{video_name}_signal.csv` — raw 470 nm + 405 nm fluorescence, ~60 Hz
- Z-scored (30 Hz): `NEW_vame/{video_name}_aligned.csv` `signal` column — session-level z-score
  aligned to video frames; exact preprocessing unconfirmed (r ≈ 0.86 with dF/F; provenance
  not fully traceable from available files); included for publication reproducibility
- Only 31 of 161 sessions (all in `oft_fp` experiment)
- Custom interface: `FiberPhotometryInterface` via ndx-fiber-photometry
- NWB storage:
  - `processing/ophys/FiberPhotometrySeriesDfOverF` — canonical dF/F at ~60 Hz (unit: a.u.)
  - `processing/ophys/FiberPhotometrySeriesZScored` — z-scored at 30 Hz (unit: z-score)
  - `acquisition/FiberPhotometrySeriesRawSignal` — raw 470 nm at ~60 Hz
  - `acquisition/FiberPhotometrySeriesIsosbesticControl` — raw 405 nm at ~60 Hz

### Aligned Analysis
- Format: CSV merging all data streams at 30 Hz
- Location: `NEW_vame/{video_name}_aligned.csv` (161 files, one per session)
- Replaces previous `aligned_157/` and `aligned_36/` directories
- Kinematics columns extracted: speed, acceleration, angular.speed, distance.moved,
  angular.distance, speed_snout, distance.moved_snout
- Custom interface: `AlignedDataInterface` → `BehavioralTimeSeries`

## Session/Subject Mapping (from details.csv)

- 161 sessions total
- 7 sub-experiments: oft_6OHDA, oft_anti_anxa1, oft_fp, oft_mitopark_10-11weeks,
  oft_mitopark_15-18weeks, oft_Tetx, oft_6ohda_tailStriatum
- Groups: asc_acid, 6OHDA, anxi-anxa1, anxa1-flp, dat-cre, dLight_dStr (→dCP), dLight_vStr (→cCP),
  Ctrl 10-11 wks, KO 10-11 wks, KO 15-18 wks, Ctrl 15-18 wks, ctrl, Tetx, asc.acid_ts, 6ohda_ts
- Lines: WT, Anxa1-flp/DAT-cre, anxa1-flp, dat-cre, DAT-cre/Tfam

## Stream Coverage

| Stream                   | Sessions |
|--------------------------|----------|
| Video                    | 161      |
| Pose estimation          | 161      |
| VAME motifs (42-motif)   | ~157     |
| VAME latent vectors      | ~157     |
| Fiber photometry (dF/F)     | 31       |
| Fiber photometry (z-scored) | 31       |
| Fiber photometry (raw)      | 31       |
| Aligned (NEW_vame)       | 161      |

## Session Naming
- 87 sessions use `tmaze_` prefix despite being OFT experiments (legacy naming)
- 74 sessions use `oft_` prefix
- Both follow the pattern: `{prefix}_{YYYY-MM-DD}T{HH_MM_SS}`
- Timezone: Europe/Stockholm (Karolinska Institutet)

## Decisions
- Videos stored as external references (not embedded in NWB)
- Only kinematics columns extracted from aligned CSV (pose/motifs/signal handled by dedicated interfaces)
- Dots in column names (e.g., `angular.speed`) converted to underscores for NWB
- Sex extracted from aligned CSV when available, otherwise "U"
- VAME motif files use `42_km_label_` prefix (k-means clustering step), but the HMM algorithm
  (stored in `config["parameterization"]`) is used as the `MotifSeries.algorithm` field because
  HMM is the final segmentation step applied on top of the k-means embedding.
- `MotifSeries` name is overridden to the plain `"MotifSeries"` (the NeuroConv interface
  auto-generates `"MotifSeriesKmeans"` from the run key; the plain name is set in `convert_session.py`
  for readability). The run key `"kmeans"` remains the dict key used internally.
- `pose_estimation_metadata_key` is injected into `metadata["Behavior"]["VAMEProjects"]["VAME_42"]`
  after `converter.get_metadata()` — it is not a constructor argument in the new interface.
