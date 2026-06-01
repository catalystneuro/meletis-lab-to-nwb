# Video Conversion: AVI to MP4

## Why convert AVI to MP4?

Behavioral videos in this dataset are recorded as `.avi` files encoded with MPEG-4 Part 2.
While these files play fine on most desktop  applications, **AVI files cannot be streamed
in a web browser** and are therefore not supported by [Neurosift](https://neurosift.app), the web-based NWB
file viewer used to inspect data on DANDI.

Neurosift streams and plays video directly inside the browser using the browser's native
`<video>` element. Browsers universally support H.264-encoded MP4 (`.mp4`) but do not
support AVI containers or MPEG-4 Part 2 video. As a result:

- AVI videos attached to NWB files will **not play** when you open the file on Neurosift
- MP4 (H.264) videos **play immediately** in the browser with no download required

We therefore transcode all `.avi` videos to `.mp4` before NWB conversion so the resulting
DANDI assets are fully Neurosift-compatible.

## Conversion details

The script uses [ffmpeg](https://ffmpeg.org) with the following settings:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Codec | `libx264` (H.264) | Universal browser support |
| Preset | `medium` | Balanced encode speed vs. file size |
| CRF | `18` | Near-lossless quality (0 = lossless, 51 = worst) |
| Pixel format | `yuv420p` | Required for QuickTime / most decoders |
| Audio | stripped (`-an`) | Behavioral videos have no audio |

CRF 18 produces visually indistinguishable output from the source at a substantially
smaller file size than the original MPEG-4 Part 2 encoding.

## Requirements

Install `ffmpeg` before running the script. It must be available on your `PATH`.

**macOS (Homebrew):**
```bash
brew install ffmpeg
```

**Linux (apt):**
```bash
sudo apt install ffmpeg
```

**Conda (cross-platform):**
```bash
conda install -c conda-forge ffmpeg
```

Verify the installation:
```bash
ffmpeg -version
```

## Running the script

The conversion script is located at:
```
src/meletis_lab_to_nwb/video/convert_avi_to_mp4.py
```

Edit the paths at the bottom of the file to match your local data layout, then run:

```bash
python src/meletis_lab_to_nwb/video/convert_avi_to_mp4.py
```

By default the script is configured for the water-consumption dataset:

```python
data_dir_path = Path("/Volumes/T9/data/Meletis/water_consumption")
videos_dir = data_dir_path / "videos"        # source AVI files
output_dir = data_dir_path / "videos_mp4"    # converted MP4 files written here
```

Change `data_dir_path` (and `videos_dir` / `output_dir` if needed) to point to a
different experiment's video folder.

The script:
1. Finds all `.avi` files in `videos_dir` (ignores macOS resource-fork files starting with `._`)
2. Skips any file whose output `.mp4` already exists (safe to re-run)
3. Writes converted files to `output_dir`, creating it if it does not exist
4. Returns the list of output paths so the function can be called programmatically from
   a conversion script

### Calling from a conversion script

You can also import and call the function directly:

```python
from pathlib import Path
from meletis_lab_to_nwb.video.convert_avi_to_mp4 import convert_avi_to_mp4_h264

avi_files = sorted(Path("/data/videos").glob("*.avi"))
mp4_paths = convert_avi_to_mp4_h264(
    video_file_paths=avi_files,
    output_directory=Path("/data/videos_mp4"),
)
```
