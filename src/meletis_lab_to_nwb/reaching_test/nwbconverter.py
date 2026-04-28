"""Primary NWBConverter class for the reaching_test (forelimb reaching) experiment."""

from neuroconv import NWBConverter
from neuroconv.datainterfaces import DeepLabCutInterface, ExternalVideoInterface

from ..interfaces import ReachingBehaviorInterface


class ReachingTestNWBConverter(NWBConverter):
    """Primary conversion class for the reaching test.

    Combines the lateral behavior video (by external reference), DeepLabCut pose
    estimation, and manually-scored reach annotations. The ``Behavior`` interface is
    optional: sessions in which the mouse did not perform any reach attempts have no
    annotation CSV and should be constructed without the ``Behavior`` source entry.
    """

    data_interface_classes = dict(
        Video=ExternalVideoInterface,
        PoseEstimation=DeepLabCutInterface,
        Behavior=ReachingBehaviorInterface,
    )
