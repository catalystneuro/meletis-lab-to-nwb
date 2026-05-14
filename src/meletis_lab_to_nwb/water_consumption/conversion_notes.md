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

- `fp_dat`    → jGCaMP8m axonal signals in dCP; virus injected into SNc (pGP-AAV9-CAG-FLEX-jGCaMP8m-WPRE, Addgene #162381, DAT-Cre).
- `fp_anxa1`  → jGCaMP8m axonal signals in dCP; virus injected into SNc (AAV-DJ/2-hSyn1-chl-dFRT-jGCaMP8m(rev)-dFRT-WPRE-bGHp, VVF Zurich, Anxa1-Flp).
- `dLight_dStr` → dLight1.3b in dorsal caudoputamen (dCP; AP +0.74, ML ±1.5, DV −2.2). Confirmed by lab.
- `dLight_vStr` → dLight1.3b in central caudoputamen (cCP; AP +0.38, ML +2.0, DV −2.9). Confirmed by lab.

## Storage + alignment

- Both FP streams use the CSV-provided timestamps (raw `time` column and processed `Time(s)`
  column). **Confirmed by the lab**: Bonsai starts the video and synchronizes the FP system
  simultaneously, so the FP clock and video frame clock share the same origin. No extra
  alignment is needed.
- Event times from `annotations/*.csv` are computed as `frame / 60.0`. **60 fps confirmed
  by the lab for all sessions** (FLIR camera). See open_questions.md W1 for the manuscript
  resolution discrepancy (paper states 800 × 800; actual files are 1440 × 1080 — paper correction
  needed).

## Files produced per conversion

Per session: `nwb_output/water_consumption/sub-<mouse.ID>/sub-<mouse.ID>_ses-<session_id>.nwb`.
