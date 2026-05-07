"""Shared DataInterface for forelimb-reaching behavior annotation CSVs.

Used by both the water-consumption (forelimb reaching-for-water) and the reaching-test
conversions. Both experiments share the same manual-annotation CSV format, the same
ndx-events AnnotatedEventsTable output schema, and the same Doric/FLIR hardware setup.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from ndx_events import AnnotatedEventsTable
from neuroconv.basedatainterface import BaseDataInterface
from neuroconv.datainterfaces.behavior.video.video_utils import get_video_timestamps
from neuroconv.tools.nwb_helpers import get_module
from neuroconv.utils import DeepDict, calculate_regular_series_rate, dict_deep_update, load_dict_from_file
from pynwb import NWBFile

# Canonical column set. Raw CSVs sometimes encode pixel-distance columns with dots
# instead of parentheses; we normalize to this schema before writing.
RICH_COLUMNS = [
    "frame",
    "paw",
    "event.type",
    "target.x",
    "target.y",
    "paw.x",
    "paw.y",
    "reference(px)",
    "distance(px)",
    "distance(cm)",
]

# Superset of all normalization variants seen across both experiments.
EVENT_TYPE_NORMALIZATION = {
    "C": "correct",
    "correct": "correct",
    "M": "miss",
    "miss": "miss",
    "missed": "miss",
    "E": "empty",
    "empty": "empty",
    "emopty": "empty",
    "drop": "drop",
    "semidrop": "semidrop",
    "semi-drop": "semidrop",
}

PAW_NORMALIZATION = {
    "L": "left",
    "left": "left",
    "R": "right",
    "right": "right",
    "mouth": "mouth",
}

DEFAULT_EVENT_TYPE_DESCRIPTIONS = {
    "correct": "Successful reach: paw contacted spout and retrieved the water droplet.",
    "miss": "Reach attempt that did not contact the spout.",
    "empty": "Reach directed at an empty spout (no water available).",
    "drop": "Water was grasped but dropped before retrieval.",
    "semidrop": "Partial drop: some water retrieved, some lost.",
    "unknown": "Reach whose outcome was not annotated or whose code was unrecognized.",
}


class ReachingBehaviorInterface(BaseDataInterface):
    """DataInterface for forelimb-reaching behavior annotation CSVs.

    Each row of the annotation CSV is a manually-scored reach event identified by its
    video frame index. Sessions with rich annotations also carry target/paw pixel
    coordinates and a distance-to-spout measurement; sessions with minimal annotations
    only provide ``frame``, ``paw``, and ``event.type``.

    Frame indices are converted to event times using the video frame rate. Because the
    converter sets ``session_start_time`` to the video start time,
    ``frame / frame_rate`` is directly seconds since session start.

    Events are stored in an ``AnnotatedEventsTable`` (ndx-events 0.2.2) named
    ``reaching_events``: one row per event type with ragged ``event_times`` and ragged
    per-event metadata columns (paw, frame, target/paw pixel coordinates, distances —
    NaN for sessions without rich annotations).
    """

    keywords = ("behavior", "reaching", "water reward")

    def __init__(
        self,
        file_path: str | Path,
        video_file_path: str | Path,
        metadata_yaml_path: str | Path = None,
        verbose: bool = True,
    ):
        self.metadata_yaml_path = Path(metadata_yaml_path)
        super().__init__(file_path=file_path, video_file_path=video_file_path, verbose=verbose)

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        if self.metadata_yaml_path.exists():
            behavior_metadata = load_dict_from_file(self.metadata_yaml_path)
            metadata = dict_deep_update(metadata, behavior_metadata)
        return metadata

    def get_metadata_schema(self) -> dict:
        schema = super().get_metadata_schema()
        schema.setdefault("properties", {})
        behavior_schema = schema["properties"].setdefault(
            "Behavior",
            {"type": "object", "additionalProperties": False, "properties": {}},
        )
        behavior_schema.setdefault("properties", {})
        behavior_schema["properties"]["ReachingEvents"] = {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "EventTypes": {"type": "object", "additionalProperties": True, "properties": {}},
                "Columns": {"type": "object", "additionalProperties": True, "properties": {}},
            },
        }
        return schema

    def add_to_nwbfile(self, nwbfile: NWBFile, metadata: dict | None = None, stub_test: bool = False) -> None:
        # utf-8-sig strips the BOM that appears on some session CSV headers.
        df = pd.read_csv(self.source_data["file_path"], encoding="utf-8-sig")

        column_rename = {
            "reference.px.": "reference(px)",
            "distance.px.": "distance(px)",
            "distance.cm.": "distance(cm)",
        }
        df = df.rename(columns=column_rename)
        for col in RICH_COLUMNS:
            if col not in df.columns:
                df[col] = np.nan
        df = df[RICH_COLUMNS].copy()

        df = df.dropna(subset=["frame"]).reset_index(drop=True)
        df["frame"] = df["frame"].astype(int)

        df["event.type"] = (
            df["event.type"].fillna("unknown").map(lambda v: EVENT_TYPE_NORMALIZATION.get(str(v), "unknown"))
        )
        df["paw"] = df["paw"].fillna("unknown").map(lambda v: PAW_NORMALIZATION.get(str(v), "unknown"))

        if stub_test:
            df = df.head(5)

        if df.empty:
            return

        timestamps = get_video_timestamps(file_path=self.source_data["video_file_path"])
        if (frame_rate := calculate_regular_series_rate(timestamps)) is not None:
            df["_event_time"] = df["frame"].to_numpy(dtype=int) / frame_rate
        else:
            raise ValueError("Cannot determine frame rate for event time conversion, video timestamps are irregular.")

        df = df.sort_values("_event_time").reset_index(drop=True)

        meta = (metadata or {}).get("Behavior", {}).get("ReachingEvents", {})
        table_name = meta.get("name", "reaching_events")
        table_description = meta.get("description") or (
            "Manually-scored reaching events from the forelimb reaching-for-water task. "
            "Stored as an ndx-events AnnotatedEventsTable: one row per event type, with a "
            "ragged 'event_times' column (seconds relative to session_start_time, computed "
            f"as frame_index / {frame_rate:g} Hz) and ragged per-event metadata columns "
            "(paw, frame, target/paw pixel coordinates, distances — NaN for sessions with "
            "minimal annotations)."
        )

        event_type_descriptions = meta.get("EventTypes", {})
        column_descriptions = meta.get("Columns", {})

        def _col_desc(key: str, default: str) -> str:
            entry = column_descriptions.get(key, {})
            return entry.get("description", default) if isinstance(entry, dict) else default

        def _event_type_desc(label: str) -> str:
            entry = event_type_descriptions.get(label, {})
            default = DEFAULT_EVENT_TYPE_DESCRIPTIONS.get(label, f"Reach event of type '{label}'.")
            return entry.get("description", default) if isinstance(entry, dict) else default

        reach_events = AnnotatedEventsTable(
            name=table_name,
            description=table_description,
            resolution=1.0 / frame_rate,
        )

        grouped = df.groupby("event.type", sort=True)
        frames_ragged: list[list[int]] = []
        paws_ragged: list[list[str]] = []
        target_x_ragged: list[list[float]] = []
        target_y_ragged: list[list[float]] = []
        paw_x_ragged: list[list[float]] = []
        paw_y_ragged: list[list[float]] = []
        reference_px_ragged: list[list[float]] = []
        distance_px_ragged: list[list[float]] = []
        distance_cm_ragged: list[list[float]] = []

        for event_type, group in grouped:
            group = group.sort_values("_event_time")
            reach_events.add_event_type(
                label=str(event_type),
                event_description=_event_type_desc(str(event_type)),
                event_times=group["_event_time"].to_numpy().astype(float),
            )
            frames_ragged.append(group["frame"].astype(int).tolist())
            paws_ragged.append(group["paw"].astype(str).tolist())
            target_x_ragged.append(group["target.x"].astype(float).tolist())
            target_y_ragged.append(group["target.y"].astype(float).tolist())
            paw_x_ragged.append(group["paw.x"].astype(float).tolist())
            paw_y_ragged.append(group["paw.y"].astype(float).tolist())
            reference_px_ragged.append(group["reference(px)"].astype(float).tolist())
            distance_px_ragged.append(group["distance(px)"].astype(float).tolist())
            distance_cm_ragged.append(group["distance(cm)"].astype(float).tolist())

        reach_events.add_column(
            name="frame",
            description=_col_desc("frame", "Annotated video frame index (0-based) for each event."),
            data=frames_ragged,
            index=True,
        )
        reach_events.add_column(
            name="paw",
            description=_col_desc(
                "paw",
                "Body part that contacted the spout for each event: 'left', 'right', 'mouth', or 'unknown'.",
            ),
            data=paws_ragged,
            index=True,
        )
        reach_events.add_column(
            name="target_x",
            description=_col_desc(
                "target_x", "Spout target x-position in pixels for each event (NaN if not annotated)."
            ),
            data=target_x_ragged,
            index=True,
        )
        reach_events.add_column(
            name="target_y",
            description=_col_desc(
                "target_y", "Spout target y-position in pixels for each event (NaN if not annotated)."
            ),
            data=target_y_ragged,
            index=True,
        )
        reach_events.add_column(
            name="paw_x",
            description=_col_desc(
                "paw_x",
                "Paw x-position in pixels at each event (video frame origin top-left, x increases right; "
                "NaN if not annotated).",
            ),
            data=paw_x_ragged,
            index=True,
        )
        reach_events.add_column(
            name="paw_y",
            description=_col_desc(
                "paw_y",
                "Paw y-position in pixels at each event (video frame origin top-left, y increases down; "
                "NaN if not annotated).",
            ),
            data=paw_y_ragged,
            index=True,
        )
        reach_events.add_column(
            name="reference_px",
            description=_col_desc(
                "reference_px",
                "Pixel reference distance used for cm conversion, per event (NaN if not annotated).",
            ),
            data=reference_px_ragged,
            index=True,
        )
        reach_events.add_column(
            name="distance_px",
            description=_col_desc(
                "distance_px", "Reach distance to spout in pixels for each event (NaN if not annotated)."
            ),
            data=distance_px_ragged,
            index=True,
        )
        reach_events.add_column(
            name="distance_cm",
            description=_col_desc(
                "distance_cm", "Reach distance to spout in cm for each event (NaN if not annotated)."
            ),
            data=distance_cm_ragged,
            index=True,
        )

        behavior_module = get_module(nwbfile, name="behavior", description="processed behavioral data")
        behavior_module.add(reach_events)
