"""Primary NWBConverter class for the arrow maze choice task."""

from neuroconv import NWBConverter
from neuroconv.datainterfaces import DeepLabCutInterface, ExternalVideoInterface


class ArrowMazeChoiceTaskNWBConverter(NWBConverter):
    """Primary conversion class for the arrow maze choice task dataset."""

    data_interface_classes = dict(
        Video=ExternalVideoInterface,
        PoseEstimation=DeepLabCutInterface,
    )
