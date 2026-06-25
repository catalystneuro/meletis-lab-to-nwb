"""Primary NWBConverter class for the open field test."""

from neuroconv import NWBConverter
from neuroconv.datainterfaces import DeepLabCutInterface, ExternalVideoInterface

from .behaviorinterface import OpenFieldTestBehaviorInterface
from .vameinterface import VameInterface
from ..interfaces import FiberPhotometryInterface


class OpenFieldTestNWBConverter(NWBConverter):
    """Primary conversion class for the open field test dataset."""

    data_interface_classes = dict(
        Video=ExternalVideoInterface,
        PoseEstimation=DeepLabCutInterface,
        VAME=VameInterface,
        FiberPhotometry=FiberPhotometryInterface,
        Behavior=OpenFieldTestBehaviorInterface,
    )
