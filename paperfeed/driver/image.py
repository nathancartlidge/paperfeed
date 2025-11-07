from dataclasses import dataclass
from functools import cached_property

import numpy as np
import PIL.Image

from paperfeed.driver.constants import FunnyPackets


@dataclass(frozen=True)
class Image:
    density: int
    data: np.ndarray[np.bool] | PIL.Image.Image

    def __post_init__(self):
        if isinstance(self.data, PIL.Image.Image):
            width = self.data.width
        else:
            width = self.data.shape[1]
        assert width == 384, f"invalid width (got {self.data.shape[1]}, wanted 384)"

    @cached_property
    def as_numpy(self) -> np.ndarray[np.bool]:
        if isinstance(self.data, np.ndarray):
            return self.data
        elif isinstance(self.data, PIL.Image.Image):
            # account for the flipped printing direction
            rotated = self.data.rotate(angle=180)
            data_array = np.array(rotated)
            assert data_array.dtype == bool, (
                f"expected dtype bool but got {data_array.dtype}"
            )
            return data_array
        else:
            raise TypeError(f"Unsupported type {type(self.data)}")

    @property
    def funny_height(self):
        return round(self.as_numpy.shape[0] / 2)

    @property
    def start_messages(self) -> list[bytearray]:
        return [
            FunnyPackets.density(self.density),
            FunnyPackets.start_print(num_lines=self.funny_height),
        ]

    @property
    def end_messages(self) -> list[bytearray]:
        return [FunnyPackets.end_print(num_lines=self.funny_height)]

    @property
    def line_packets(self) -> list[bytearray]:
        height, width = self.as_numpy.shape
        assert width == 384, f"invalid width (got {width}, wanted 384)"

        lines: list[bytes] = []
        for line in self.as_numpy:
            bits = np.packbits(line, bitorder="big")
            lines.append(bits.tobytes())

        if len(lines) % 2 == 1:
            lines.append(FunnyPackets.BLANK_LINE)

        funny_lines = [
            FunnyPackets.print_line(i, top + bot)
            for i, (top, bot) in enumerate(zip(lines[::2], lines[1::2]))
        ]
        assert len(funny_lines) == self.funny_height, (
            f"incorrect line count (got {len(funny_lines)}, wanted {self.funny_height})"
        )

        return funny_lines
