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

## Session/Subject Mapping (from details_tmaze_updated.csv)

- The conversion reads `details_tmaze_updated.csv`, which fills in the sex and date of birth that
  `details.csv` lacks for 32 sessions. Two mice (583415, 720084; 8 sessions) have no date of birth or
  sex in either table. On the lab's instruction their files carry the age range stated in the paper
  (`age = "P2M/P6M"`, 2 to 6 months) in place of a date of birth, and sex `U`.
- `group`, `experiment` and `day` are also stored in `lab_meta_data["session_metadata"]`
  (`group`, `cohort`, `day`)
- 168 sessions total, 42 mice x 4 days
- Two sub-experiments:
  - `tmaze_6ohda`: 14 mice (WT line), groups: 6ohda vs asc.acid
  - `tmaze_anxa1_tet`: 28 mice (anxa1-flp line), groups: anxa1_tet vs ctrl
- Session start time encoded in filename: `tmaze_YYYY-MM-DDTHH_MM_SS`
- Timezone: Europe/Stockholm

## Ontology Annotation (HERD)

`external_resources.yaml` links values in the files to external terms. The converter writes them as HERD
references (`nwbfile.external_resources`) with `meletis_lab_to_nwb/external_resources.py`. Every id was
checked in its registry.

- Species `Mus musculus`: NCBITaxon:10090.
- Institution `Karolinska Institutet`: ROR:056d84691.
- Experimenters: Mantas, Ioannis (ORCID 0000-0001-6288-5439), Contestabile, Alessandro
  (ORCID 0000-0001-6528-1403), Skara, Vasiliki (ORCID 0000-0002-0017-6116). The ORCIDs are in the
  Crossref author lists of two Meletis lab papers (10.1126/sciadv.adx9450, 10.1101/2025.09.09.675138).
- Strain: wild-type subjects (genotype `WT`) are written with strain `C57BL/6NCrl` and linked to
  RRID:IMSR_CRL:027, because the paper's Methods say the C57BL/6N mice came from Charles River. Transgenic
  subjects keep strain `C57BL/6N` without a term. DAT-Cre is probably RRID:IMSR_JAX:006660, but the paper
  does not name the source, so it waits for the lab to confirm. Anxa1-Flp (a new line made for the paper)
  and the Tfam loxP (MitoPark) line have no RRID.
- Pose-estimation keypoints (UBERON): snout 0006333, head 0000033, leftFrontPaw and rightFrontPaw
  0002398 (manus), leftBackPaw and rightBackPaw 0002387 (pes). `body` (the body center) and `tailBase`
  have no UBERON term and are not linked.
