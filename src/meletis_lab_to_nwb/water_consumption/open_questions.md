# Open questions for the Meletis lab — water_consumption (reaching task) conversion

Each item: the question, why it matters for the conversion, what we're currently doing, and
the evidence behind the default.

---

## ~~W1. Is every behavior video recorded at 60 fps?~~ ✓ Resolved

**Confirmed by the lab**: all sessions were recorded at **60 fps** with a FLIR camera.
`ReachingBehaviorInterface` default of `video_frame_rate_hz=60.0` is correct for all sessions.

**Note — manuscript resolution discrepancy**: The manuscript (lines 910–911) states
"60 fps, 800 × 800" but all 59 videos report **1440 × 1080** via ffprobe. The lab confirmed
the FLIR camera was used; the 800 × 800 figure in the manuscript needs to be corrected before
publication. The NWB conversion uses the actual file resolution.

---

## ~~W2. GCaMP variant, AAV, and fiber location for `fp_dat` / `fp_anxa1`~~ ✓ Resolved

**Confirmed by the lab and cross-referenced with Mantas et al. 2026 (lines 621–628):**

- **Indicator**: jGCaMP8m for both groups (ref 101 = Dana et al. 2019, Nat. Methods 16, 649-657)
- **fp_dat** (DAT-Cre): pGP-AAV9-CAG-FLEX-jGCaMP8m-WPRE (Addgene #162381), 300 nL unilateral
  injection into SNc
- **fp_anxa1** (Anxa1-Flp): AAV-DJ/2-hSyn1-chl-dFRT-jGCaMP8m(rev)-dFRT-WPRE-bGHp (VVF Zurich),
  300–500 nL unilateral injection into SNc

**Fiber placement**: confirmed by the lab as **dCP (AP +0.74, ML ±1.5, DV −2.2)** for both
groups. The virus is injected into the SNc to label the neurons, but the fiber optic cannula
is implanted in the dorsal caudoputamen to record GCaMP signals from the striatal
projections of those SN neurons. All updated in `convert_session.py` and
`fiber_photometry_metadata.yaml`.

---

## ~~W3. Does `dLight_vStr` correspond to cCP or NAc?~~ ✓ Resolved

**Confirmed by the lab**: `dLight_vStr` → **cCP** (central caudoputamen) and `dLight_dStr` →
**dCP** (dorsal caudoputamen), consistent with the manuscript nomenclature and matching the
resolution of the same question in the opto+dLight conversion. Updated in `convert_session.py`,
`fiber_photometry_metadata.yaml`, `conversion_notes.md`, and the demo notebook.

---

## ~~W4. Are there sessions without manual annotations, or with empty spout ≡ no reach?~~ ✓ Resolved

**Confirmed by the lab**: for sessions with ≤5 annotated events, the low count a true reflection
of behavior.
Across 59 annotation files, the event count per session ranges from **2 to 82**
(median 27). Some sessions have very few events (e.g., `low signal`, `learning`, `very few
trials` noted in `details.csv.obs`).

---

## ~~W5. Alignment between the behavior video and the fiber photometry stream~~ ✓ Resolved

**Confirmed by the lab**: Bonsai starts the video recording and simultaneously synchronizes
the fiber photometry system at session start. No additional alignment step is needed.
The FP `Time(s)` timestamps and the behavior video frame indices share the same clock
origin, so `frame / 60.0` directly gives seconds relative to the FP timeline.

---
