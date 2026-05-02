import math
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import numpy.typing as npt
import PIL.Image
import PIL.ImageChops

from paperfeed.driver.constants import FunnyPackets
from paperfeed.text import to_1_bit


@dataclass(frozen=True)
class Image:
    density: int
    data: npt.NDArray[np.bool] | PIL.Image.Image

    def __post_init__(self):
        if isinstance(self.data, PIL.Image.Image):
            width = self.data.width
        else:
            width = self.data.shape[1]
        assert width == 384, f"invalid width (got {width}, wanted 384)"

    @classmethod
    def from_file(
        cls,
        file: Path | str,
        threshold: int = 128,
        use_dithering: bool = False,
        trim_margins: bool = False,
        trim_colour: float | tuple[int, ...] | None = None,
        density: int = 4,
    ):
        file_path = Path(file)
        img = PIL.Image.open(file_path)

        if trim_margins:
            # trim white margins
            img_rgb = img.convert("RGB")
            margin_colour = trim_colour or img.getpixel((0, 0))
            margin_img = PIL.Image.new("RGB", img.size, margin_colour)
            diff = PIL.ImageChops.difference(img_rgb, margin_img)
            # prevent issues with compression artifacts
            # adapted from https://stackoverflow.com/questions/10615901/trim-whitespace-using-pil
            diff = PIL.ImageChops.add(diff, diff, 1.0, -192)
            bbox = diff.getbbox()
            if bbox:
                img = img.crop(bbox)

        scaling_factor = 384 / img.width
        img_small = img.resize((384, round(scaling_factor * img.height)))
        return cls(
            density=density,
            data=to_1_bit(img_small, threshold=threshold, use_dithering=use_dithering),
        )

    @cached_property
    def as_numpy(self) -> npt.NDArray[np.bool]:
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
    def funny_height(self) -> int:
        return math.ceil(self.as_numpy.shape[0] / 2)

    @property
    def start_messages(self) -> list[bytes]:
        return [
            FunnyPackets.density(self.density),
            FunnyPackets.start_print(num_lines=self.funny_height),
        ]

    @property
    def end_messages(self) -> list[bytes]:
        return [FunnyPackets.end_print(num_lines=self.funny_height)]

    @property
    def line_packets(self) -> list[bytes]:
        height, width = self.as_numpy.shape
        assert width == 384, f"invalid width (got {width}, wanted 384)"

        lines: list[bytes] = []
        for line in self.as_numpy:
            # line should be provided in inverse format
            bits = np.packbits(~line, bitorder="big")
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
