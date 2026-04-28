# Conversion notes — water_consumption (forelimb reaching-for-water task)

## Dataset summary

- **Path**: `/Volumes/T9/data/Meletis/water_consumption/`
- **Sessions**: 59 (1:1:1:1 mapping between `videos/`, `signal/`, `signal_df/`, and `annotations/`)
- **Subjects**: 25 mice
- **Groups (from `details.csv.group`)**: `fp_dat`, `fp_anxa1`, `dLight_dStr`, `dLight_vStr`
- **Lines (from `details.csv.line`)**: `dat_cre`, `anxa1-flp`
- **Design**: 4 consecutive 15-min training days per mouse (per manuscript, Mantas et al. 2026, lines 892–910).

## Data streams

| Stream | Path | Per-session filename | Notes |
|--------|------|----------------------|-------|
| Behavior video | `videos/` | `<video_stem>.avi` | MPEG-4, 1440×1080, 60 fps, ~21 min, ~8.7 GB each |
| Raw fiber photometry | `signal/` | `<video_stem>_signal.csv` | Columns: `time`, `ref` (405 nm), `sig` (470 nm). ~60 Hz sampling. Starts at ~7 s. |
| Processed dF/F fiber photometry | `signal_df/` | `<video_stem>_signal_df.csv` | Columns: `Time(s)` and a motion-corrected dF/F column named after the underlying signal/reference values. |
| Manual reach annotations | `annotations/` | `<video_stem>_behavior.csv` | Sparse (median ~27 rows/session). Frame-indexed events with paw + outcome metadata. |
| Session metadata | `details.csv` | (top-level) | mouse.ID, video, group, line, sex, DoB, obs, has_avi, has_signal_df, has_behavior |

## Annotation schema variants

4 column schemas across 59 files:

| Schema | Files | Columns |
|--------|-------|---------|
| Rich (canonical) | 18 | `frame, paw, event.type, target.x, target.y, paw.x, paw.y, reference(px), distance(px), distance(cm)` |
| Minimal | 39 | `frame, paw, event.type` |
| Rich (dot-separated variant) | 1 | Same as rich but `reference.px.`, `distance.px.`, `distance.cm.` — renamed in the interface |
| Rich + 5 trailing empty `Unnamed` columns | 1 | Rich + stripped trailing NaN columns |

All variants are unified to the rich schema in `behaviorinterface.py`; missing columns are filled with NaN.

**Value sets observed across the dataset**:

- `paw`: `mouth` (746), `right` (204), `left` (139), NaN (495) → NaN normalized to `"unknown"`.
- `event.type`: `correct` (661), `miss` (202), `empty` (151), `drop` (66), `missed` (4, typo for `miss`), `semidrop` (4), `emopty` (1, typo for `empty`), NaN (495).

Known typos (`missed` → `miss`, `emopty` → `empty`) are normalized in the interface; `semidrop` is kept verbatim.

## Conversion architecture

Following the `opto_dlight` pattern:

- `WaterConsumptionNWBConverter` aggregates three interfaces: `FiberPhotometry`, `Behavior`, `Video` (ExternalVideoInterface — the .avi is referenced, not copied).
- `FiberPhotometryInterface` subclasses `opto_dlight.FiberPhotometryInterface` and only overrides the metadata YAML path. The CSV formats are identical between the two experiments.
- `ReachingBehaviorInterface` parses the annotation CSV, converts frame indices to event times using the video frame rate, and writes a `TimeIntervals` table named `reaching_events` with custom columns for paw, event_type, target/paw coordinates, and distance.

## Per-session metadata dispatch

`convert_session.py` uses `GROUP_FP_CONFIG` to override the indicator / location based on
`details.csv.group`:

- `fp_dat`    → GCaMP in SN compact part (DAT-Cre pan-DA labeling). **Exact GCaMP variant unconfirmed — see open_questions.md W2.**
- `fp_anxa1`  → GCaMP in SN compact part (Anxa1-Flp Anxa1+ DAN subpopulation). **Same caveat.**
- `dLight_dStr` → dLight1.3b in Caudoputamen (dCP target from the manuscript).
- `dLight_vStr` → dLight1.3b in Caudoputamen (provisionally cCP — carried-over ambiguity from the opto+dLight conversion, see open_questions.md).

## Storage + alignment

- Both FP streams use the CSV-provided timestamps (raw `time` column and processed `Time(s)`
  column). Per the analogous opto+dLight inspection, those timestamps are on the same clock
  as the behavior video (session starts at t=0 = video start).
- Event times from `annotations/*.csv` are computed as `frame / 60.0`. If the video frame
  rate differs from 60 Hz for some sessions (older sessions?) this will skew event times —
  see open_questions.md W1.

## Files produced per conversion

Per session: `nwb_output/water_consumption/sub-<mouse.ID>/sub-<mouse.ID>_ses-<session_id>.nwb`.
