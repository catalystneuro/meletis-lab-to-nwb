import subprocess
from pathlib import Path


def convert_avi_to_mp4_h264(
    *,
    video_file_paths: list[Path],
    output_directory: Path,
) -> list[Path]:
    """Transcode each .avi (MPEG-4 part 2) to .mp4 (H.264) via system ffmpeg.

    Writes to output_directory / <source_stem>.mp4. Skips files whose output
    already exists. Returns the list of converted paths in input order.
    """
    output_directory.mkdir(parents=True, exist_ok=True)

    converted_paths = []
    for source_path in video_file_paths:
        source_path = Path(source_path)
        output_path = output_directory / f"{source_path.stem}.mp4"
        converted_paths.append(output_path)

        if output_path.exists():
            print(f"Skipping video conversion (already exists): {output_path}")
            continue

        print(f"Converting {source_path.name} -> {output_path.name} (H.264 MP4)...")
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-y",
                "-i",
                str(source_path),
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-an",
                str(output_path),
            ],
            check=True,
        )

    return converted_paths


if __name__ == "__main__":
    data_dir_path = Path("/Volumes/T9/data/Meletis/water_consumption")
    videos_dir = data_dir_path / "videos"
    output_dir = data_dir_path / "videos_mp4"

    avi_files = sorted(p for p in videos_dir.glob("*.avi") if not p.name.startswith("._"))
    print(f"Found {len(avi_files)} AVI files to convert.")

    convert_avi_to_mp4_h264(
        video_file_paths=avi_files,
        output_directory=output_dir,
    )
