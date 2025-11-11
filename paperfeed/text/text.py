import logging
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

from paperfeed.text.utils import to_1_bit
from paperfeed.text.constants import LINE_WIDTH


class Text:
    def __init__(self, file: Path | str):
        """
        Create a font class
        :param file: a path to the font file (if str, relative to this file)
        """
        if isinstance(file, str) and "/" not in file and "\\" not in file:
            self._file = (Path(__file__).parent / file).resolve()
        else:
            self._file = Path(file).resolve()

        self._logger = logging.getLogger(
            self.__class__.__name__ + "::" + self._file.stem
        )
        self._logger.info("Loading font data from %s", self._file)
        with open(self._file, "rb") as f:
            self._font_data = f.read()

    @lru_cache(maxsize=2)
    def at_size(self, size: int | float) -> FreeTypeFont:
        """
        Render the heading font at a given size.

        :param size: (float) The size (in points) of the font to fetch
        :return FreeTypeFont (rendered to bitmap?) at the given size

        This method uses BytesIO to reduce disk I/O when loading fonts repeatedly
        """
        font_stream = BytesIO(self._font_data)
        return ImageFont.truetype(font=font_stream, size=size)

    def render(self, text: str) -> Image.Image:
        """Base render method (to be overwritten by child classes). Maps text to an image"""
        font = self.at_size(24)
        image = self._render_text(font, text)
        return image

    @staticmethod
    def _render_text(
        font: FreeTypeFont,
        text: str,
        width: int = LINE_WIDTH,
        height: int = 100,
    ) -> Image.Image:
        """
        (static method) Render text to a Pillow Image
        :param font:
        :param text:
        :param width:
        :param height:
        :param pad_x:
        :return:
        """
        bbox = font.getbbox(text)
        image = Image.new("L", (width, height), 0)

        draw = ImageDraw.Draw(image)
        draw.text((-bbox[0], 1 - bbox[1]), text=text, font=font, fill=255)

        return to_1_bit(image)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    f = Text("roboto.ttf")
    img = f.render(text="Hello, World!")
    img.show()
