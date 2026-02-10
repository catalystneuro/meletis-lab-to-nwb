"""Primary NWBConverter class for this dataset."""

from neuroconv import NWBConverter
from neuroconv.datainterfaces import (
    PhySortingInterface,
    SpikeGLXRecordingInterface,
)

from meletis_lab_to_nwb.arrow_maze_choice_task import ArrowMazeChoiceTaskBehaviorInterface


class ArrowMazeChoiceTaskNWBConverter(NWBConverter):
    """Primary conversion class for my extracellular electrophysiology dataset."""

    data_interface_classes = dict(
        Recording=SpikeGLXRecordingInterface,
        Sorting=PhySortingInterface,
        Behavior=ArrowMazeChoiceTaskBehaviorInterface,
    )
