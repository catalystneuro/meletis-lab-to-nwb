# Notes concerning the opto+dLight conversion

## Data Location
`/Volumes/T9/data/Meletis/opto+dLight/`

## File Structure
```
opto+dLight/
├── details.csv                              # Session metadata (20 rows)
├── TTL/
│   ├── oft_2024-03-01T10_16_32.csv          # 20 TTL files (no header: timestamp, sample, bool)
│   └── ...
└── signal/
    ├── oft_2024-03-01T10_16_32_signal_df.csv # 20 fiber photometry signal files
    └── ...
```

## Data Streams

### Optogenetic Stimulation (TTL)
- Format: CSV, no header, 3 columns: ISO timestamp (+01:00 timezone), sample index, boolean
- Sampling rate: ~143 Hz (measured from data; comment in code saying ~30 Hz is incorrect)
- Duration: ~1100-1260s per session
- Each True value is a brief 1-sample pulse (~7 ms); consecutive True samples separated by < 1s are grouped into one burst
- The first burst of True values = fiber photometry system activation (excluded)
- Subsequent bursts = nosepoke-triggered laser stimulation episodes (~1-6s per burst depending on nosepoke clustering)
- Protocol: 40 Hz laser, 1s stimulation + 3s inter-stimulation interval
- NeuroConv interface: Custom `OptogeneticsTTLInterface` → `OptogeneticSeries` + `TimeIntervals`
- Clock synchronization: FP clock and TTL clock are synchronized to within 7 ms (verified by matching FP start at ~8.117s with first TTL True at ~8.124s)

### Fiber Photometry (dLight)
- Format: CSV, 2 columns: `Time(s)` and motion-corrected signal (sig - ref)
- Sampling rate: ~60 Hz
- Timestamps start at ~8s (fiber photometry system warm-up)
- Indicator: dLight1.3b (dopamine sensor)
- NeuroConv interface: Custom `FiberPhotometryInterface` via ndx-fiber-photometry

## Session/Subject Mapping (from details.csv)

- 20 sessions total, 4 mice (776769, 776770, 802369, 802372)
- All anxa1-flp line
- Two recording sites:
  - `dStr` (dorsal striatum): mice 776769, 776770 (10 sessions)
  - `vStr` (ventral striatum): mice 802369, 802372 (10 sessions)
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
- `obs` column in details.csv is "TRUE" for some sessions (meaning unclear, not used)
- `has_TTL` column is blank for vStr sessions in details.csv but TTL files exist for all 20 sessions
- Typo in details.csv column name: `intenisty` (should be `intensity`)
