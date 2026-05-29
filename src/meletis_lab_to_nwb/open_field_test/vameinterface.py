"""Local VameInterface for the open field test conversion."""

import json
from pathlib import Path

import numpy as np
from neuroconv import BaseTemporalAlignmentInterface
from neuroconv.tools import get_module
from neuroconv.utils import DeepDict, calculate_regular_series_rate, load_dict_from_file
from pydantic import FilePath, validate_call
from pynwb import NWBFile


class VameInterface(BaseTemporalAlignmentInterface):
    """DataInterface for VAME behavioral segmentation data using the ndx-vame NWB extension."""

    display_name = "VAME"
    keywords = ("VAME", "behavioral motifs", "pose segmentation")
    associated_suffixes = (".npy", ".yaml")
    info = "Interface for adding data from VAME (Variational Animal Motion Encoding)."

    _timestamps = None

    @classmethod
    def get_source_schema(cls) -> dict:
        source_schema = super().get_source_schema()
        source_schema["properties"]["motif_labels_file_path"]["description"] = (
            "Path to the .npy file containing VAME motif labels "
            "(1D int array, one cluster ID per video frame). "
            "Typically named '{n_clusters}_{algorithm}_label_{session}.npy'."
        )
        source_schema["properties"]["latent_vectors_file_path"]["description"] = (
            "Path to the .npy file containing VAME latent-space vectors "
            "(2D float32 array of shape (n_frames, n_latent_dims)). "
            "Typically named 'latent_vectors.npy'. Optional."
        )
        source_schema["properties"]["community_labels_file_path"]["description"] = (
            "Path to the .npy file containing VAME community labels "
            "(1D int array, one community ID per video frame). "
            "Typically named 'cohort_community_label_{session}.npy'. Optional."
        )
        source_schema["properties"]["vame_config_file_path"]["description"] = (
            "Path to the VAME 'config.yaml' project file. "
            "When provided, project metadata are serialized into the NWB file. Optional."
        )
        return source_schema

    @validate_call
    def __init__(
        self,
        motif_labels_file_path: FilePath,
        latent_vectors_file_path: FilePath | None = None,
        community_labels_file_path: FilePath | None = None,
        vame_config_file_path: FilePath | None = None,
        sampling_frequency_hz: float | None = None,
        vame_project_metadata_key: str = "VAMEProject",
        pose_estimation_name: str | None = None,
        verbose: bool = False,
    ):
        import ndx_vame  # noqa: F401 – ensure ndx-vame namespace is registered

        self.motif_labels_file_path = Path(motif_labels_file_path)
        self.latent_vectors_file_path = Path(latent_vectors_file_path) if latent_vectors_file_path else None
        self.community_labels_file_path = Path(community_labels_file_path) if community_labels_file_path else None
        self.sampling_frequency_hz = sampling_frequency_hz
        self.vame_project_metadata_key = vame_project_metadata_key
        self.pose_estimation_name = pose_estimation_name

        self.vame_config_dict = {}
        if vame_config_file_path is not None:
            self.vame_config_dict = load_dict_from_file(vame_config_file_path)

        super().__init__(
            motif_labels_file_path=motif_labels_file_path,
            latent_vectors_file_path=latent_vectors_file_path,
            community_labels_file_path=community_labels_file_path,
            vame_config_file_path=vame_config_file_path,
            verbose=verbose,
        )

    def get_metadata_schema(self) -> dict:
        from neuroconv.utils import get_base_schema

        metadata_schema = super().get_metadata_schema()

        motif_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "algorithm": {"type": ["string", "null"]},
            },
            "required": ["name"],
        }
        community_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "algorithm": {"type": ["string", "null"]},
            },
            "required": ["name"],
        }

        vame_schema = get_base_schema(tag="VAME")
        vame_schema["additionalProperties"] = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "MotifSeries": motif_schema,
                "LatentSpaceSeries": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                },
                "CommunitySeries": community_schema,
            },
            "required": ["name"],
            "additionalProperties": False,
        }

        metadata_schema["properties"]["VAME"] = vame_schema
        return metadata_schema

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()

        # Extract algorithm from VAME config ('parameterization' field, e.g. 'hmm').
        algorithm = self.vame_config_dict.get("parameterization") or None

        vame_project_metadata: dict = dict(
            name=self.vame_project_metadata_key,
            MotifSeries=dict(
                name="MotifSeries",
                description="VAME behavioral motif labels.",
                algorithm=algorithm,
            ),
        )

        if self.latent_vectors_file_path is not None:
            zdims = self.vame_config_dict.get("zdims")
            dims_info = f" ({zdims} dimensions per frame)" if zdims else ""
            vame_project_metadata["LatentSpaceSeries"] = dict(
                name="LatentSpaceSeries",
                description=f"VAME latent-space embeddings{dims_info}.",
            )

        if self.community_labels_file_path is not None:
            vame_project_metadata["CommunitySeries"] = dict(
                name="CommunitySeries",
                description="VAME community labels grouping motifs into higher-level behavioral states.",
                algorithm=algorithm,
            )

        metadata["VAME"] = {self.vame_project_metadata_key: vame_project_metadata}
        return metadata

    def get_original_timestamps(self) -> np.ndarray:
        if self.sampling_frequency_hz is None:
            raise ValueError(
                "VameInterface cannot generate original timestamps without a sampling_frequency_hz. "
                "Provide sampling_frequency_hz at construction or call set_aligned_timestamps()."
            )
        n_frames = len(np.load(self.motif_labels_file_path))
        return np.arange(n_frames) / self.sampling_frequency_hz

    def get_timestamps(self) -> np.ndarray:
        return self._timestamps if self._timestamps is not None else self.get_original_timestamps()

    def set_aligned_timestamps(self, aligned_timestamps: np.ndarray) -> None:
        self._timestamps = np.asarray(aligned_timestamps)

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        stub_test: bool = False,
    ) -> None:
        from ndx_vame import (
            CommunitySeries,
            LatentSpaceSeries,
            MotifSeries,
            VAMEProject,
        )

        default_metadata = DeepDict(self.get_metadata())
        if metadata is not None:
            default_metadata.deep_update(metadata)

        vame_metadata = default_metadata["VAME"][self.vame_project_metadata_key]
        project_name = vame_metadata["name"]
        motif_metadata = vame_metadata["MotifSeries"]

        n_frames = min(100, len(self.get_timestamps())) if stub_test else None

        timestamps = self.get_timestamps()[:n_frames]
        rate = calculate_regular_series_rate(series=timestamps)

        timing_kwargs = {}
        if rate is None:
            timing_kwargs["timestamps"] = timestamps.astype(np.float64)
        else:
            timing_kwargs["rate"] = float(rate)
            timing_kwargs["starting_time"] = timestamps[0]

        latent_series = None
        latent_series_metadata = vame_metadata.get("LatentSpaceSeries")
        if self.latent_vectors_file_path is not None and latent_series_metadata is not None:
            latent_data = np.load(self.latent_vectors_file_path)[:n_frames].astype(np.float32)
            latent_series = LatentSpaceSeries(
                data=latent_data,
                **latent_series_metadata,
                **timing_kwargs,
            )

        motif_data = np.load(self.motif_labels_file_path)[:n_frames].astype(np.int32)
        motif_kwargs: dict = dict(data=motif_data, **motif_metadata, **timing_kwargs)
        if latent_series is not None:
            motif_kwargs["latent_space_series"] = latent_series
        motif_series = MotifSeries(**motif_kwargs)

        community_series = None
        community_metadata = vame_metadata.get("CommunitySeries")
        if self.community_labels_file_path is not None and community_metadata is not None:
            community_data = np.load(self.community_labels_file_path)[:n_frames].astype(np.int32)
            community_series = CommunitySeries(
                data=community_data,
                **community_metadata,
                **timing_kwargs,
                motif_series=motif_series,
            )

        pose_estimation = None
        behavior_module = get_module(nwbfile, name="behavior", description="Processed behavioral data.")
        if self.pose_estimation_name is not None:
            pose_estimation = behavior_module.data_interfaces.get(self.pose_estimation_name)

        vame_project = VAMEProject(
            name=project_name,
            pose_estimation=pose_estimation,
            latent_space_series=latent_series,
            motif_series=motif_series,
            community_series=community_series,
            vame_config=json.dumps(self.vame_config_dict),
        )

        behavior_module.add(vame_project)
