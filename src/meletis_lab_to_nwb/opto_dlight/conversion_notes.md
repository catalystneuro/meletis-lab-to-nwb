# Notes concerning the opto+dLight conversion

## Data Location
`.../Meletis/opto+dLight/`

## Experiment summary

Water-restricted Anxa1-Flp mice (n=4) freely nosepoked to trigger bilateral SNc laser stimulation
(640 nm, ChRmine, 40 Hz, 1 s bursts). Striatal dopamine was recorded simultaneously with dLight1.3b fiber photometry
at two sites (dCP, cCP). Five laser intensities tested per animal (0.1, 0.2, 0.5, 1, 2 mW).
Corresponds to Extended Data Fig. 7F–J.

## File Structure
```
opto+dLight/
├── details.csv                              # Session metadata (20 rows)
├── TTL/
│   ├── oft_2024-03-01T10_16_32.csv          # 20 TTL files (no header: timestamp, sample, bool)
│   └── ...
└── signal/
    ├── oft_2024-03-01T10_16_32_signal.csv    # 20 raw acquisition files (time, ref, sig)
    ├── oft_2024-03-01T10_16_32_signal_df.csv # 20 processed dF/F files
    └── ...
```

## Data Streams

### Optogenetic Stimulation (TTL)
- Format: CSV, no header, 3 columns: (1) ISO wall-clock timestamp, (2) frame (0-indexed), (3) boolean TTL state
- **Column 1 is NOT used for timing** — confirmed by Meletis lab: individual wall-clock timestamps are not accurate per sample
- **Time basis**: session start parsed from filename (`oft_YYYY-MM-DDTHH_MM_SS`); per-sample time = `frame_index / frame_rate`;
- Sampling rate: OptogeneticsTTLInterface conversion option `video_frame_rate` set to 30.0 Hz (confirmed by Meletis lab)
- Duration: ~1100-1260s per session
- Each True value is a brief 1-sample pulse (~7 ms); consecutive True samples separated by < 1s are grouped into one burst
- The first burst of True values = fiber photometry system activation (excluded)
- Subsequent bursts = nosepoke-triggered laser stimulation episodes (~1-6s per burst depending on nosepoke clustering)
- Protocol: 40 Hz laser, 1s stimulation + 3s inter-stimulation interval
- NeuroConv interface: Custom `OptogeneticsTTLInterface` → `OptogeneticSeries` + `TimeIntervals`
- Clock alignment: TTL t=0 is session start (from filename); FP `Time(s)` starts at ~8.1 s (system warm-up). Both clocks originate from Bonsai session start, so the ~8.1 s FP offset and the first TTL True (~8.1 s) remain aligned.

### Fiber Photometry (dLight)
- **Raw acquisition** (`*_signal.csv`): 3 columns — `time`, `ref` (405 nm isosbestic), `sig` (470 nm signal), arbitrary fluorescence units. Stored as `FiberPhotometryResponseSeries` and `FiberPhotometryResponseSeriesIsosbestic` in `nwbfile.acquisition`.
- **Processed dF/F** (`*_signal_df.csv`): 2 columns — `Time(s)` and motion-corrected dF/F (sig - ref). Stored as `DfOverFFiberPhotometryResponseSeries` in `processing/ophys/`.
- Sampling rate: ~60 Hz
- Timestamps start at ~8s (fiber photometry system warm-up)
- Indicator: dLight1.3b (dopamine sensor)
- NeuroConv interface: Custom `FiberPhotometryInterface` via ndx-fiber-photometry
- `FiberPhotometryTable` has 2 rows: row 0 = 470 nm signal channel, row 1 = 405 nm isosbestic reference

## Session/Subject Mapping (from details.csv)

- 20 sessions total, 4 mice (776769, 776770, 802369, 802372)
- All anxa1-flp line
- Two recording sites (details.csv `group` codes → article nomenclature):
  - `dStr` → `dCP` (dorsal caudoputamen): mice 776769, 776770 (10 sessions)
  - `vStr` → `cCP` (central caudoputamen): mice 802369, 802372 (10 sessions)
- 5 intensities per mouse pair: 0.1, 0.2, 0.5, 1, 2 mW
- Session timestamp encoded in filename: `oft_YYYY-MM-DDTHH_MM_SS`
- Timezone: Europe/Stockholm (Karolinska Institutet)

## Decisions
- First TTL burst excluded (fiber photometry system activation, not real stimulation)
- OptogeneticSeries stores power in watts (NWB standard unit) with rate from TTL sampling
- Stimulation episodes stored as TimeIntervals (start/stop per nosepoke-triggered burst)
- Laser power stored as the session's intensity when TTL is True, 0 when False
- dLight1.3b used as indicator label (dopamine sensor)
- Sex set to "U" (not tracked per subject in the dataset)

## Open Questions / Data to Request

- **Confirm first TTL burst interpretation**: The current code excludes the first burst of TTL
  True values (~8.124s → ~14.275s, ~6s duration) on the assumption that it corresponds to
  fiber photometry system activation rather than real optogenetic stimulation. This was inferred
  from data inspection only (timing coincides with FP warm-up at ~8.117s; `start.fp` column in
  details.csv equals the first TTL True sample index; burst is ~6s vs ~1s for real stim episodes)
  — it is **not stated in the manuscript**. Ask the lab to confirm whether this interpretation is
  correct. If wrong, the first real stimulation episode is being silently discarded for every session.

- **Raw nosepoke events from Bonsai**: The current dataset only contains the laser TTL trace
  (on/off state at ~143 Hz). Successful nosepokes can be inferred from `stimulation_episodes`
  start times, but raw port-entry events (including pokes during the 3s ISI lockout that
  did NOT trigger stimulation) are not available. Ask the lab whether Bonsai saved a separate
  nosepoke event log (e.g., `*_nosepoke.csv`, `*_port.csv`, or another Bonsai output stream)
  and include it as a `BehavioralEvents` or `TimeIntervals` table in the NWB file if available.

## Known Issues
- `start.fp` column in details.csv matches the sample index of the first TTL True value
- `has_TTL` column is blank for cCP (vStr) sessions in details.csv but TTL files exist for all 20 sessions
- Typo in details.csv column name: `intenisty` (should be `intensity`)
