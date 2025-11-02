from dataclasses import dataclass

import numpy as np


from paperfeed.driver.constants import FunnyPackets


@dataclass(frozen=True)
class Image:
    density: int
    data: np.ndarray[np.bool]

    def __post_init__(self):
        assert self.data.shape[1] == 384, f"invalid width (got {self.data.shape[1]}, wanted 384)"

    @property
    def funny_height(self):
        return round(self.data.shape[0] / 2)

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
        height, width = self.data.shape
        assert width == 384, f"invalid width (got {width}, wanted 384)"

        lines: list[bytes] = []
        for line in self.data:
            bits = np.packbits(line, bitorder="big")
            lines.append(bits.tobytes())

        if len(lines) % 2 == 1:
            lines.append(FunnyPackets.BLANK_LINE)

        funny_lines = [
            FunnyPackets.print_line(i, top + bot)
            for i, (top, bot) in enumerate(zip(lines[::2], lines[1::2]))
        ]
        assert len(funny_lines) == self.funny_height, f"incorrect line count (got {len(funny_lines)}, wanted {self.funny_height})"

        return funny_lines
