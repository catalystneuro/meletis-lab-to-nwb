"""Primary NWBConverter class for the arrow maze choice task."""

from pathlib import Path

from neuroconv import NWBConverter
from neuroconv.datainterfaces import DeepLabCutInterface, ExternalVideoInterface
from neuroconv.utils import load_dict_from_file

from ..external_resources import add_external_resources


class ArrowMazeChoiceTaskNWBConverter(NWBConverter):
    """Primary conversion class for the arrow maze choice task dataset."""

    data_interface_classes = dict(
        Video=ExternalVideoInterface,
        PoseEstimation=DeepLabCutInterface,
    )

    def add_to_nwbfile(self, nwbfile, metadata, conversion_options=None):
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        terms = load_dict_from_file(Path(__file__).parent / "external_resources.yaml")
        add_external_resources(nwbfile=nwbfile, terms=terms)
