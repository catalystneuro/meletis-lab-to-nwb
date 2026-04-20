# Notes concerning the arrow_maze_choice_task conversion

## File Structure
```
tmaze/
├── details.csv                          # Session metadata (video, mouse.ID, group, line, day, experiment)
├── videos/
│   ├── tmaze_2022-03-22T15_08_03.mp4    # 168 MP4 files
│   └── ...
└── pose_estimation/
    ├── tmaze_2022-03-22T15_08_03.csv    # 168 DLC CSV files (1:1 with videos)
    └── ...
```

## Data Streams

### Video
- Format: H.264 MP4, 856x818, 30 fps
- Duration: 10 min per session (18000 frames)
- Size: ~0.29 GB per file
- NeuroConv interface: `ExternalVideoInterface`

### Pose Estimation (DeepLabCut)
- Format: CSV with standard DLC multi-header (scorer/bodyparts/coords)
- Scorer: `DLC_resnet50_completeArrowMazeDec9shuffle1_1000000`
- 8 keypoints: snout, head, leftFrontPaw, rightFrontPaw, leftBackPaw, rightBackPaw, body, tailBase
- Each row = one frame; columns = x, y, likelihood per keypoint
- 18000 rows per file (matches video frame count)
- No DLC config file available (not needed — CSVs parse fine without it)
- NeuroConv interface: `DeepLabCutInterface`

## Session/Subject Mapping (from details.csv)

- 168 sessions total, 42 mice x 4 days
- Two sub-experiments:
  - `tmaze_6ohda`: 14 mice (WT line), groups: 6ohda vs asc.acid
  - `tmaze_anxa1_tet`: 28 mice (anxa1-flp line), groups: anxa1_tet vs ctrl
- Session start time encoded in filename: `tmaze_YYYY-MM-DDTHH_MM_SS`
- Timezone: Europe/Stockholm
