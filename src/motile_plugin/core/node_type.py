from enum import Enum


class NodeType(Enum):
    SPLIT = "SPLIT"
    END = "END"
    MERGE = "MERGE"
    START = "START"
    CONTINUE = "CONTINUE"
