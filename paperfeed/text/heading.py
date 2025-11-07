import logging
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.ImageFont import FreeTypeFont

from paperfeed.text.utils import to_1_bit


class HeadingText:
    def __init__(
        self,
        file: Path | str,
        target_width: int = 384,
        min_size: int = 10,
        max_size: int = 750,
        size_step: float = 0.1,
    ):
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

        self._target_width: int = target_width
        self._size_step: float = size_step
        self._sizes: tuple[float, float] = (min_size, max_size)

    def render_text(
        self, text: str, split_size: float = 128, target_gap: int = 16
    ) -> Image.Image:
        font = self.get_size(split_size)
        words = text.split()

        current_line: list[str] = []
        lines: list[str] = []
        for word in words:
            current_line.append(word)
            bbox = font.getbbox(" ".join(current_line))
            width = bbox[2] - bbox[0]
            if width >= self._target_width and len(current_line) > 1:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))

        images = []
        for line in lines:
            line_img, gap = self.render_line(line, target_gap=target_gap)
            images.append((line_img, gap))

        total_height = sum(img.height for img, _ in images) + sum(
            gap for _, gap in images[:-1]
        )
        image = Image.new("L", (self._target_width, total_height), 0)

        offset = 0
        for line_img, gap in images:
            image.paste(line_img, (0, offset))
            offset += line_img.height + gap

        return to_1_bit(image)

    def render_line(self, text: str, target_gap: int) -> tuple[Image.Image, int]:
        """render a line of text to fill a given width"""
        best_size = self._get_best_size(text)
        font = self.get_size(best_size)

        bbox = font.getbbox(text)
        img_width = round(bbox[2] - bbox[0])
        img_height = round(bbox[3] - bbox[1])
        left_pad = (self._target_width - img_width) // 2

        gap = target_gap

        # attempt to prevent weird characters from making the gap inconsistent
        nonalpha_chars = "".join([c for c in text if c.isalnum() or c == " "])
        if nonalpha_chars and nonalpha_chars != text:
            bbox_alpha = font.getbbox(nonalpha_chars)
            if bbox_alpha:
                na_height = round(bbox_alpha[3] - bbox_alpha[1])
                gap = max(gap // 2, gap - (img_height - na_height))
                self._logger.debug("gap is %d (%d / %d)", gap, na_height, img_height)

        image = self._render(font, text, self._target_width, img_height, left_pad)

        return image, gap

    def get_size(self, size: int | float) -> FreeTypeFont:
        """
        Render the heading font at a given size.

        :param size: (float) The size (in points) of the font to fetch
        :return FreeTypeFont (rendered to bitmap?) at the given size

        This method uses BytesIO to reduce disk I/O when loading fonts repeatedly
        """
        font_stream = BytesIO(self._font_data)
        return ImageFont.truetype(font=font_stream, size=size)

    def _get_best_size(self, text: str, max_iterations: int = 20) -> float:
        """determine the 'optimal' font size using binary search"""
        self._logger.info("determining best size for %s", text)
        min_size, max_size = self._sizes
        best_size: float = min_size
        size = sum(self._sizes) / 2

        iteration = 0
        use_ratio: bool = True
        while min_size <= max_size and iteration < max_iterations:
            self._logger.debug("iteration %d, attempting size %f", iteration, size)
            font = self.get_size(size)
            img = self._render(
                font, text=text, width=self._target_width + 200, height=500
            )
            bbox = img.getbbox()
            if bbox is None:
                raise ValueError(
                    f"Render {iteration} (size={size}) produced an invalid bbox"
                )
            img_width = int(bbox[2] - bbox[0])

            if img_width == self._target_width:
                best_size = size
                self._logger.debug("got target size")
                break

            self._logger.debug("got %d, wanted %d", img_width, self._target_width)
            if img_width < self._target_width:
                best_size = size
                min_size = size + self._size_step
            else:
                max_size = size - self._size_step

            if use_ratio and abs(self._target_width - img_width) > 2:
                ratio = self._target_width / img_width
                size = min(max(size * ratio, min_size), max_size)
                self._logger.debug("ratio = %f", ratio)
            else:
                if use_ratio:
                    self._logger.debug("swapping to binary search")
                    min_size = max(min_size, size - 8)
                    max_size = min(max_size, size + 8)
                    use_ratio = False

                size = (min_size + max_size) / 2

            # clamp size to min/max sizes
            iteration += 1

        if iteration == max_iterations:
            self._logger.warning("hit maximum iterations")

        return best_size

    @staticmethod
    def _render(
        font: FreeTypeFont, text: str, width: int, height: int, pad_x: int = 0
    ) -> Image.Image:
        bbox = font.getbbox(text)
        img = Image.new("L", (width, height), 0)

        draw = ImageDraw.Draw(img)
        draw.text((pad_x - bbox[0], -bbox[1]), text=text, font=font, fill=255)

        return img


if __name__ == "__main__":
    # Usage
    logging.basicConfig(level=logging.INFO)
    f = HeadingText("bebas_neue.ttf")
    img = f.render_text(text="Hello, World!", split_size=96)
    img.save("render.png")
