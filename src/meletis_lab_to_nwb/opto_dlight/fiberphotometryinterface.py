"""DataInterface for fiber photometry signal data (opto+dLight experiment)."""

from pathlib import Path

from neuroconv.utils import DeepDict, dict_deep_update, load_dict_from_file

from meletis_lab_to_nwb.interfaces import FiberPhotometryInterface as _BaseFiberPhotometryInterface


class FiberPhotometryInterface(_BaseFiberPhotometryInterface):
    """FiberPhotometryInterface for the opto+dLight experiment.

    Inherits all recording logic from
    :class:`~meletis_lab_to_nwb.interfaces.FiberPhotometryInterface` and loads
    opto+dLight-specific metadata (device descriptions, per-line indicator mapping
    for Anxa1-Flp and DAT-Cre mice) from the local ``fiber_photometry_metadata.yaml``.

    The motion-corrected dF/F signal is stored as a ``DfOverFFiberPhotometryResponseSeries``
    inside the ``ophys`` processing module (``processing/ophys/``). When a raw acquisition
    file is supplied (``raw_file_path``), raw 470 nm and 405 nm traces are stored in
    ``nwbfile.acquisition``.
    """

    keywords = ("fiber photometry", "dopamine", "dLight")

    def get_metadata(self) -> DeepDict:
        metadata = super().get_metadata()
        fp_metadata_path = Path(__file__).parent / "fiber_photometry_metadata.yaml"
        fp_metadata = load_dict_from_file(fp_metadata_path)
        return dict_deep_update(metadata, fp_metadata)
