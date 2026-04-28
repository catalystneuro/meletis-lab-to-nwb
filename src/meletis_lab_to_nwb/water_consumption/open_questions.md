# Open questions for the Meletis lab — water_consumption (reaching task) conversion

Each item: the question, why it matters for the conversion, what we're currently doing, and
the evidence behind the default.

---

## W1. Is every behavior video recorded at 60 fps?

**Question.** All 59 videos we inspected (`ffprobe`) report 1440 × 1080 @ 60 fps. The
manuscript (Mantas et al. 2026, lines 910–911) describes a FLIR camera at **60 fps, 800 × 800**
for the reaching task. The frame rate matches, but the resolution does not. Were earlier
sessions (e.g. the 2023 batch) recorded on a different camera or at a different frame rate?

**Why it matters.** Event times in the NWB file are computed as
`frame_index / video_frame_rate_hz` in `ReachingBehaviorInterface`. A wrong frame rate
(e.g. 30 fps instead of 60) would shift every annotated event by 2×.

**Current behavior.** `ReachingBehaviorInterface` defaults `video_frame_rate_hz=60.0` for
every session. If any session was recorded at a different rate, we need a per-session
override (easy: parse via ffprobe at conversion time).

**What to ask.** Can the lab confirm that every session was recorded at 60 fps? If not,
which sessions differ and at what frame rate?

---

## W2. Which GCaMP variant + AAV is used for the `fp_dat` and `fp_anxa1` cohorts?

**Question.** Four `group` values appear in `details.csv`:
- `dLight_dStr` and `dLight_vStr`: the manuscript describes these (dLight1.3b via AAV5-CAG-dLight1.3b, Addgene #125560).
- `fp_dat` and `fp_anxa1`: the manuscript text does **not** specify which calcium indicator
  and AAV were used for SN DAN cell-body recordings in this cohort. The bibliography
  includes a high-performance GCaMP reference (Dana et al. 2019, ref 101), which suggests
  GCaMP7 — but this is not tied explicitly to the reaching-task cohort.

**Why it matters.** The NWB `Indicator` object needs a concrete label (e.g. `GCaMP7f`,
`jGCaMP8m`), a manufacturer (Addgene + plasmid ID), and a construct/AAV description.
Without this, the fp_dat and fp_anxa1 sessions will be published with a placeholder
`indicator_label: "GCaMP"` and a description noting the uncertainty.

**Current behavior.** `convert_session.py.GROUP_FP_CONFIG` sets
`indicator_label = "GCaMP"` and a description that flags the uncertainty. The
`Indicator.description` field stays generic.

**What to ask.**
- Exact GCaMP variant for the SN cell-body recordings in the reaching task
  (GCaMP7f, jGCaMP8m, etc.)?
- AAV construct used (serotype, promoter, Cre/Flp dependence) and manufacturer / plasmid ID?
- Injection coordinates and volume for SN DANs in this cohort?

---

## W3. Does `dLight_vStr` in `details.csv` correspond to cCP or to NAc?

**Question.** Carried over from the opto+dLight conversion. The manuscript describes two
striatal dLight targets (**dCP** and **cCP**, both in the caudoputamen; lines 628-629,
656-658). `details.csv` uses the shorthand `vStr`, which could mean either "central CP"
(consistent with the manuscript) or "ventral striatum" = nucleus accumbens (inconsistent
with the manuscript but a common neuroanatomy convention).

**Why it matters.** The Allen Atlas location field in the NWB file is different
(`Caudoputamen` vs `Nucleus accumbens`). The wrong label would mislead downstream users.

**Current behavior.** `convert_session.py.GROUP_FP_CONFIG["dLight_vStr"]` maps to
`Caudoputamen` on the assumption that `vStr` is a lab shorthand for cCP. See the analogous
question in `opto_dlight/open_questions.md` item 2.

**What to ask.** Does `dLight_vStr` correspond to the manuscript's cCP target (caudoputamen)
or to a separate nucleus-accumbens cohort that isn't described in the paper?

---

## W4. Are there sessions without manual annotations, or with empty spout ≡ no reach?

**Observation.** Across 59 annotation files, the event count per session ranges from **2 to 82**
(median 27). Some sessions have very few events (e.g., `low signal`, `learning`, `very few
trials` noted in `details.csv.obs`).

**Why it matters.** A session with 2 annotated events is either (a) a training day with low
engagement (the mouse didn't reach much) or (b) an incomplete annotation pass. The NWB file
shouldn't conflate the two.

**What to ask.** For sessions with ≤5 annotated events, is the low count a true reflection
of behavior, or are there additional unscored reaches?

---

## W5. What is the definition of each `event.type` value?

**Observation.** Observed values: `correct`, `miss`, `empty`, `drop`, `semidrop`,
`missed` (4 rows, appears to be a typo for `miss`), `emopty` (1 row, typo for `empty`).

**Why it matters.** These categorical labels become part of the NWB `event_type` column
with user-facing descriptions. We've guessed definitions (correct = successful grasp,
miss = no contact, empty = reach at empty spout, drop = water dropped after grasp,
semidrop = partial drop) but they are not stated in the manuscript methods.

**Current behavior.** `behaviorinterface.py.EVENT_TYPE_NORMALIZATION` folds `missed` →
`miss` and `emopty` → `empty`. `semidrop` is kept verbatim (4 occurrences).

**What to ask.** Can the lab confirm the operational definition of each `event.type`
value, and confirm that `missed`/`emopty` are indeed typos for `miss`/`empty`?

---

## W6. Alignment between the behavior video and the fiber photometry stream

**Observation.** Fiber photometry timestamps in `*_signal_df.csv` start at ~7 s and run at
~60 Hz; the video also runs at 60 fps and presumably starts at t=0 for the same session.

**Why it matters.** We assume the FP `Time(s)` column and the behavior video are on the
same clock (both started by Bonsai when the session began). If there's a hardware latency
between FP start and video start, events annotated at frame N would not line up with the FP
trace sample at time `N / 60`. Same logic as the `start.fp` discovery in the opto+dLight
conversion.

**Why no `start.fp` here?** `details.csv` for water_consumption does **not** have a
`start.fp` column (verified). So either (a) FP and video are assumed to start together, or
(b) alignment metadata is stored elsewhere we haven't been shown.

**What to ask.** Is there per-session alignment metadata between the behavior video and
the fiber photometry stream (a start offset, a TTL sync pulse, a second Bonsai stream)?
If not, can we treat the two clocks as synchronized?

---
