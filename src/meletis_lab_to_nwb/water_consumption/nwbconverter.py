"""Primary NWBConverter class for the water-consumption (forelimb reaching) experiment."""

from neuroconv import NWBConverter
from neuroconv.datainterfaces import ExternalVideoInterface

from ..interfaces import FiberPhotometryInterface, ReachingBehaviorInterface


class WaterConsumptionNWBConverter(NWBConverter):
    """Primary conversion class for the forelimb-reaching-for-water task with fiber photometry."""

    data_interface_classes = dict(
        FiberPhotometry=FiberPhotometryInterface,
        Behavior=ReachingBehaviorInterface,
        Video=ExternalVideoInterface,
    )
