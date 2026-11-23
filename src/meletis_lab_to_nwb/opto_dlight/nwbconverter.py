"""Primary NWBConverter class for the opto+dLight experiment."""

from pathlib import Path

from neuroconv import NWBConverter
from neuroconv.utils import load_dict_from_file

from .optogeneticsinterface import OptogeneticsTTLInterface
from ..external_resources import add_external_resources
from ..interfaces import FiberPhotometryInterface
from ..value_meanings import add_value_meanings


class OptoDlightNWBConverter(NWBConverter):
    """Primary conversion class for the optogenetic self-stimulation + dLight dataset."""

    data_interface_classes = dict(
        Optogenetics=OptogeneticsTTLInterface,
        FiberPhotometry=FiberPhotometryInterface,
    )

    def add_to_nwbfile(self, nwbfile, metadata, conversion_options=None):
        super().add_to_nwbfile(nwbfile=nwbfile, metadata=metadata, conversion_options=conversion_options)
        terms = load_dict_from_file(Path(__file__).parent / "external_resources.yaml")
        add_external_resources(nwbfile=nwbfile, terms=terms)
        annotations = load_dict_from_file(Path(__file__).parent / "value_meanings.yaml")
        add_value_meanings(nwbfile=nwbfile, annotations=annotations)
