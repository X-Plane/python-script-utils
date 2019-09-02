#!/env/bin python3
from enum import Enum


class StringEnum(Enum):
    def __str__(self):
        return self.value

    @classmethod
    def from_str(cls, string: str):
        for enum_def in cls:
            if string == enum_def.value:
                return enum_def
        raise LookupError(f'No instance of {cls} matches "{string}"')

