"""Primary NWBConverter class for the reaching_test (forelimb reaching) experiment."""

from pathlib import Path

from neuroconv import NWBConverter
from neuroconv.datainterfaces import DeepLabCutInterface, ExternalVideoInterface
from neuroconv.utils import load_dict_from_file

from ..external_resources import add_external_resources
from ..interfaces import ReachingBehaviorInterface
from ..value_meanings import add_value_meanings


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

    def add_to_nwbfile(self, nwbfile, metadata, conversion_options=None):
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        terms = load_dict_from_file(Path(__file__).parent / "external_resources.yaml")
        add_external_resources(nwbfile=nwbfile, terms=terms)
        annotations = load_dict_from_file(Path(__file__).parent / "value_meanings.yaml")
        add_value_meanings(nwbfile=nwbfile, annotations=annotations)
