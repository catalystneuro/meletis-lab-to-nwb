"""Primary NWBConverter class for the opto+dLight experiment."""

from neuroconv import NWBConverter

from .fiberphotometryinterface import FiberPhotometryInterface
from .optogeneticsinterface import OptogeneticsTTLInterface


class OptoDlightNWBConverter(NWBConverter):
    """Primary conversion class for the optogenetic self-stimulation + dLight dataset."""

    data_interface_classes = dict(
        Optogenetics=OptogeneticsTTLInterface,
        FiberPhotometry=FiberPhotometryInterface,
    )
