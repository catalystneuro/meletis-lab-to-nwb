"""DataInterface for VAME behavioral motif data."""

import json
from pathlib import Path

import numpy as np
from ndx_vame import MotifSeries, VAMEProject
from neuroconv.basedatainterface import BaseDataInterface
from pynwb import NWBFile


class VAMEInterface(BaseDataInterface):
    """DataInterface for reading VAME motif labels from .npy files and writing to NWB via ndx-vame.

    The source data contains only k-means motif-label arrays (1D int, one value per video frame).
    Latent-space embeddings and community assignments are not present in this dataset, so
    ``latent_space_series`` and ``community_series`` are always ``None``.
    """

    keywords = ("VAME", "behavioral motifs")

    def __init__(self, file_path: str | Path, name_suffix: str = "", verbose: bool = True):
        """Initialize VAMEInterface.

        Parameters
        ----------
        file_path : str or Path
            Path to the .npy file containing VAME motif labels (1D int array, one entry per
            video frame). Files are named ``47_km_label_{video_stem}.npy``; the ``47`` is the
            number of k-means clusters and the directory name (``vame_157`` / ``vame_36``) is the
            VAME latent-space dimension used during training.
        name_suffix : str, optional
            Suffix appended to the container names, e.g. ``"157"`` or ``"36"`` to distinguish
            the two VAME model variants. Produces ``VAMEMotifs157`` / ``VAMEProject157``.
        verbose : bool, optional
            Whether to print verbose output, by default True.
        """
        super().__init__(file_path=file_path, name_suffix=name_suffix, verbose=verbose)
        self.file_path = Path(file_path)
        self.name_suffix = name_suffix

    def get_metadata(self) -> dict:
        return super().get_metadata()

    def add_to_nwbfile(
        self,
        nwbfile: NWBFile,
        metadata: dict | None = None,
        pose_estimation_name: str | None = "PoseEstimationDeepLabCut",
        **kwargs,
    ) -> None:
        """Write VAME motif labels to NWB as a VAMEProject containing a MotifSeries.

        Parameters
        ----------
        nwbfile : NWBFile
            Target NWB file.
        metadata : dict, optional
            Metadata dict (unused; VAME has no additional metadata).
        pose_estimation_name : str or None, optional
            Name of the PoseEstimation object already present in the ``behavior`` processing
            module. Used to link the VAMEProject back to the pose input. Set to ``None`` to
            skip the link. Default ``"PoseEstimationDeepLabCut"``.
        """
        motif_labels = np.load(self.file_path)

        series_name = f"VAMEMotifs{self.name_suffix}" if self.name_suffix else "VAMEMotifs"
        motif_series = MotifSeries(
            name=series_name,
            data=motif_labels.astype(np.int32),
            rate=30.0,
            description=(
                f"VAME behavioral motif labels (k-means, latent dim {self.name_suffix}) — "
                "one integer label per video frame identifying the closest cluster centroid."
                if self.name_suffix
                else "VAME behavioral motif labels — one integer label per video frame."
            ),
        )

        # Link to the PoseEstimation that was used as VAME input, if it is already in the file.
        pose_estimation = None
        behavior_module = nwbfile.processing.get("behavior")
        if behavior_module is not None and pose_estimation_name is not None:
            pose_estimation = behavior_module.data_interfaces.get(pose_estimation_name)

        # latent_space_series and community_series are not available in this dataset.
        project_name = f"VAMEProject{self.name_suffix}" if self.name_suffix else "VAMEProject"
        vame_project = VAMEProject(
            name=project_name,
            pose_estimation=pose_estimation,
            latent_space_series=None,
            motif_series=motif_series,
            community_series=None,
            vame_config=json.dumps({}),
        )

        if behavior_module is None:
            behavior_module = nwbfile.create_processing_module(
                name="behavior", description="Processed behavioral data."
            )
        behavior_module.add(vame_project)
