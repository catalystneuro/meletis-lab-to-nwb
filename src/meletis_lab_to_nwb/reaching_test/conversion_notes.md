# Notes concerning the reaching-test conversion

## Data Location
`/Volumes/T9/data/Meletis/reaching_test/`

## File Structure
```
reaching_test/
├── details.csv                                          # Session metadata (~60 rows)
├── videos/
│   └── reaching_test_YYYY-MM-DDTHH_MM_SS.avi           # One video per session (60 fps, FLIR camera)
├── pose_estimation/
│   └── *DLC_resnet50_reaching_trainJun9shuffle1_100000.csv  # DeepLabCut output per session
└── annotations/
    └── *_behavior.csv                                   # Manual reach-outcome annotation per session
                                                         # Absent for sessions where mouse performed no attempts
                                                         # (details.csv `has_behavior` == FALSE)
```

## Data Streams

### Behavior Video
- Format: `.avi`, recorded laterally at 60 fps with a FLIR camera
- Stored in NWB by **external reference** (path embedded, file not copied)
- NWB location: `acquisition/BehaviorVideo` (ImageSeries)
- Session start time is derived from the video filename stem (`reaching_test_YYYY-MM-DDTHH_MM_SS`)
- NeuroConv interface: `ExternalVideoInterface`

### Manual Reach Annotations (`*_behavior.csv`)
- One row per reach attempt; columns: `frame`, `paw`, `event.type`, `target.x`, `target.y`,
  `paw.x`, `paw.y`, `reference(px)` / `reference.px.`, `distance(px)` / `distance.px.`,
  `distance(cm)` / `distance.cm.` (some sessions encode pixel-distance columns with dots instead
  of parentheses — normalized in code)
- Outcome codes: `C`→`correct`, `M`/`missed`→`miss`, `E`→`empty`, `drop`, `semidrop`/`semi-drop`→`semidrop`
- Paw codes: `L`→`left`, `R`→`right`; `mouth` passes through as-is
- Event times computed as `frame_index / frame_rate_hz` (frame rate obtained from video timestamps
  via `calculate_regular_series_rate`); session_start_time = video start time, so frame 0 → t = 0 s
- Sessions where the mouse performed no attempts have no annotation file (`has_behavior` FALSE in
  `details.csv`); those sessions are converted without the `Behavior` interface — no `reaching_events`
  table is written
- NWB location: `processing/behavior/reaching_events` (ndx-events `AnnotatedEventsTable`)
  - One row per event type with ragged `event_times`, `frame`, `paw`, `target_x`, `target_y`,
    `paw_position_ref`, `reference_px`, `distance_px`, `distance_cm`
- **Paw position SpatialSeries**: when `paw.x`/`paw.y` annotations are present, they are stored as
  a `SpatialSeries` (`processing/behavior/PawPosition/paw_position`), one sample per event in
  ascending time order, data shape `(N, 2)` in pixels. The `paw_position_ref` column of the
  `AnnotatedEventsTable` contains `TimeSeriesReference(idx_start, count=1, timeseries)` entries
  linking each event back to its row in the `SpatialSeries`
- NeuroConv interface: Custom `ReachingBehaviorInterface` (shared with `water_consumption`);
  `metadata_yaml_path` is passed explicitly from `convert_session.py` pointing to
  `reaching_test/behavior_metadata.yaml`

### DeepLabCut Pose Estimation
- Format: DLC CSV with multi-level header (scorer / keypoint / x, y, likelihood)
- Scorer: `DLC_resnet50_reaching_trainJun9shuffle1_100000`
- 8 keypoints: `snout`, `tongue`, `palm`, `wrist`, `elbow`, `mouth`, `spout`, `extra`
- Data shape per keypoint: `(n_frames, 2)` pixels + `(n_frames,)` DLC likelihood (confidence)
- Sampling rate derived from the DLC timestamps; `~55 000 frames per 15-min session ≈ 60 fps`
- NWB location: `processing/behavior/PoseEstimationReaching` (PoseEstimation container)
  - One `PoseEstimationSeries` per keypoint (e.g., `PoseEstimationSeriesPalm`)
  - `processing/behavior/Skeletons` contains `SkeletonReaching` with edges:
    palm–wrist, wrist–elbow, snout–mouth, tongue–mouth
- NeuroConv interface: `DeepLabCutInterface`; name overridden to `PoseEstimationReaching` via
  `pose_estimation_metadata.yaml`

## Session / Subject Mapping (from `details.csv`)

- ~60 sessions total across two experimental arms:
  - **`tet` / `ctrl`** — chronic silencing of Anxa1+ SNc dopamine neurons by Flp-dependent
    tetanus toxin light chain vs. littermate controls (Anxa1-Flp line)
  - **`arch_anxa1` / `arch_ctrl`** — optogenetic silencing of Anxa1+ SNc dopamine neurons with
    Archaerhodopsin vs. littermate controls (Anxa1-Flp line); sessions carry a `light` column
    (`on`, `on_after_first_reach`, `off`)
- Each mouse performs the task on multiple test days encoded in `phase`: `test1`, `test2`,
  `test4`, `test8`
- Session ID = video stem with `_` → `-`: `reaching-test-YYYY-MM-DDTHH-MM-SS`
- Timezone: Europe/Stockholm (parsed with `zoneinfo.ZoneInfo`)
- Date of birth parsed from `DoB` column (`%d-%b-%y`); left as `None` if missing/unparsable
- Sex taken from `sex` column; falls back to `"U"` if not `M` or `F`
- Genotype from `line` column (e.g., `Anxa1-flp`), capitalised

## Decisions

- Video is stored by external reference, not embedded, to keep NWB file size manageable
- `session_start_time` = video start time derived from the filename stem; this is why
  `frame_index / frame_rate` gives seconds directly relative to `session_start_time`
- Sessions with `has_behavior == FALSE` omit the `Behavior` interface entirely — no
  empty/placeholder table is written
- `paw.x` / `paw.y` per-event pixel positions are stored as a `SpatialSeries` rather than flat
  ragged columns, with a `TimeSeriesReferenceVectorData` column (`paw_position_ref`) linking the
  table back to the `SpatialSeries`; this avoids duplicating coordinate data and follows NWB
  conventions for spatial data
- DLC confidence (likelihood) stored as the `confidence` field of each `PoseEstimationSeries`;
  no threshold is applied during conversion — filtering is left to downstream analysis
- Skeleton defined with 4 edges only (limb chain + snout/tongue to mouth); the `extra` keypoint
  is a rig reference and is not connected in the skeleton

## Open Questions / Data to Request

- **R1 — Video frame rate**: The conversion assumes 60 fps for all sessions (matching the FLIR
  camera spec). The frame rate is cross-checked via `calculate_regular_series_rate` on the DLC
  timestamps, but this has not been confirmed with the lab for every session. If any session was
  recorded at a different rate the event times will be wrong.
  **Please confirm:** Were all reaching-test sessions recorded at exactly 60 fps?

- **R2 — Outcome code definitions**: The outcome codes (`C`, `M`, `E`, `drop`, `semidrop`) are
  interpreted per the water-consumption annotation conventions. The reaching-test annotation files
  use the same labels, but it has not been explicitly confirmed that the operational definitions
  (e.g., whether `empty` means no water was dispensed vs. paw missed a filled spout) are identical
  across experiments.
  **Please confirm:** Are the outcome definitions in the reaching-test annotations the same as in
  the water-consumption annotations?

- **R3 — `on_after_first_reach` light condition**: The `light` column for the Arch cohort contains
  `on_after_first_reach`, meaning the silencing laser was turned on after the first reach of the
  session. The exact trigger mechanism (manual, automated, time-locked?) is unclear from the data.
  **Please clarify:** How was the laser onset triggered in the `on_after_first_reach` condition —
  manually by the experimenter after observing the first reach on video, or via an automated
  real-time detection system?

- **Virus constructs and injection coordinates**: The `metadata.yaml` session description references
  Flp-dependent TetTox and Arch constructs but does not record AAV serotype, titre, injection
  volume, or stereotaxic coordinates. These are referenced in the manuscript (Mantas et al.) but
  are not available in `details.csv`.
  **To request:** Virus construct details (AAV serotype, plasmid ID/Addgene #, titre) and
  stereotaxic injection coordinates (AP, ML, DV from bregma) for both cohorts.

## Known Issues / Notes

- Some annotation CSVs use `distance.px.` / `distance.cm.` / `reference.px.` (dot-delimited)
  instead of `distance(px)` / `distance(cm)` / `reference(px)`; the interface normalises these
  on read
- Some event type entries use `emopty` (typo for `empty`); normalised to `empty` in
  `EVENT_TYPE_NORMALIZATION`
- The `_flatten_reaching_events` helper in the tutorial notebook (`reaching_test_demo.ipynb`)
  does **not** yet exclude `paw_position_ref` from the flat DataFrame (unlike the updated
  `water_consumption_demo.ipynb`); as a result the `reach_df` DataFrame will contain
  `TimeSeriesReference` objects in the `paw_position_ref` column, which is technically valid
  but may be confusing — this should be updated in a follow-up
