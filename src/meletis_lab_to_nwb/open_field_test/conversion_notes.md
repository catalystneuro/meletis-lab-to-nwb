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
├── vame_157/
│   ├── 47_km_label_oft_2023-05-16T15_31_06.npy  # 157 VAME motif label files
│   └── ...
├── vame_36/
│   ├── 47_km_label_oft_2023-05-16T15_31_06.npy  # 36 VAME motif label files (subset)
│   └── ...
├── signal/
│   ├── oft_2023-11-28T14_52_48_signal_df.csv  # 31 fiber photometry signal files
│   └── ...
├── aligned_157/
│   ├── oft_2023-05-16T15_31_06_aligned.csv  # 157 aligned analysis files
│   └── ...
└── aligned_36/
    ├── oft_2023-05-16T15_31_06_aligned.csv  # 36 aligned analysis files (subset)
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
- Two model variants: 157-motif (157 sessions) and 36-motif (36 sessions)
- Rate: 30 Hz (one label per video frame)
- Custom interface: `VAMEInterface` via ndx-vame `MotifSeries`

### Fiber Photometry Signal
- Format: CSV, 2 columns: `Time(s)` and signal (unique column name per file)
- Signal is motion-corrected (sig - ref)
- Sampling rate: ~60 Hz (irregular timestamps starting ~5s)
- Only 31 of 161 sessions (all in `oft_fp` experiment)
- Custom interface: `FiberPhotometryInterface` via ndx-fiber-photometry

### Aligned Analysis
- Format: CSV merging all data streams at 30 Hz
- Kinematics columns extracted: speed, acceleration, angular.speed, distance.moved,
  angular.distance, speed_snout, distance.moved_snout
- Note: `acceleration` column only present in aligned_157, not aligned_36
- Custom interface: `AlignedDataInterface` → `BehavioralTimeSeries`

## Session/Subject Mapping (from details.csv)

- 161 sessions total
- 7 sub-experiments: oft_6OHDA, oft_anti_anxa1, oft_fp, oft_mitopark_10-11weeks,
  oft_mitopark_15-18weeks, oft_Tetx, oft_6ohda_tailStriatum
- Groups: asc_acid, 6OHDA, anxi-anxa1, anxa1-flp, dat-cre, dLight_dStr (→dCP), dLight_vStr (→cCP),
  Ctrl 10-11 wks, KO 10-11 wks, KO 15-18 wks, Ctrl 15-18 wks, ctrl, Tetx, asc.acid_ts, 6ohda_ts
- Lines: WT, Anxa1-flp/DAT-cre, anxa1-flp, dat-cre, DAT-cre/Tfam

## Stream Coverage

| Stream | Sessions |
|--------|----------|
| Video | 161 |
| Pose estimation | 161 |
| VAME 157-motif | 157 |
| VAME 36-motif | 36 |
| Fiber photometry | 31 |
| Aligned 157 | 157 |

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
