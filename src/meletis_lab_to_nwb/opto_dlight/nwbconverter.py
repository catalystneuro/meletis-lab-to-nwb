"""Primary NWBConverter class for the opto+dLight experiment."""

from neuroconv import NWBConverter

from .optogeneticsinterface import OptogeneticsTTLInterface
from ..interfaces import FiberPhotometryInterface


class OptoDlightNWBConverter(NWBConverter):
    """Primary conversion class for the optogenetic self-stimulation + dLight dataset."""

    data_interface_classes = dict(
        Optogenetics=OptogeneticsTTLInterface,
        FiberPhotometry=FiberPhotometryInterface,
    )
