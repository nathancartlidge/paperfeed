import logging
from pathlib import Path

from PIL import Image

from paperfeed.text.constants import LINE_WIDTH
from paperfeed.text.text import Text


class HeadingText(Text):
    def __init__(
        self,
        file: Path | str,
        target_width: int = LINE_WIDTH,
        min_size: int = 10,
        max_size: int = 750,
        size_step: float = 0.1,
    ):
        super().__init__(file=file)

        self._target_width: int = target_width
        self._size_step: float = size_step
        self._sizes: tuple[float, float] = (min_size, max_size)

    def render(
        self, text: str, split_size: float = 128, target_gap: int = 16
    ) -> Image.Image:
        font = self.at_size(split_size)
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

        images: list[tuple[Image.Image, int, int]] = []
        for line in lines:
            line_img, gap = self._render_line(line, target_gap=target_gap)

            # check image width
            bbox = line_img.getbbox()
            line_width = int(bbox[2] - bbox[0])
            assert line_width <= self._target_width, f"line too wide, got {line_width}!"

            offset_x = (self._target_width - line_width) // 2 - bbox[0]
            self._logger.debug("x offset is %d / %s", offset_x, bbox)
            images.append((line_img, gap, offset_x))

        total_height = sum(image.height for image, _, _ in images) + sum(
            gap for _, gap, _ in images[:-1]
        )
        image = Image.new("1", (self._target_width, total_height), 0)

        offset_y = 0
        for line_img, gap, offset_x in images:
            image.paste(line_img, (offset_x, offset_y))
            offset_y += line_img.height + gap

        return image

    def _render_line(self, text: str, target_gap: int) -> tuple[Image.Image, int]:
        """render a line of text to fill a given width"""
        best_size = self._get_best_size(text)
        font = self.at_size(best_size)

        bbox = font.getbbox(text)
        img_height = 2 + round(bbox[3] - bbox[1])

        gap = target_gap

        # attempt to prevent non-alpha characters from making the gap inconsistent
        nonalpha_chars = "".join([c for c in text if c.isalnum() or c == " "])
        if nonalpha_chars and nonalpha_chars != text:
            bbox_alpha = font.getbbox(nonalpha_chars)
            if bbox_alpha:
                na_height = round(bbox_alpha[3] - bbox_alpha[1])
                gap = max(gap // 2, gap - (img_height - na_height))
                self._logger.debug("gap is %d (%d / %d)", gap, na_height, img_height)

        # render the image slightly wider to be safe - we trim later
        image = self._render_text(font, text, self._target_width + 20, img_height)

        return image, gap

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
            font = self.at_size(size)
            image = self._render_text(
                font, text=text, width=self._target_width + 200, height=500
            )
            bbox = image.getbbox()
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


if __name__ == "__main__":
    # Usage
    logging.basicConfig(level=logging.INFO)
    f = HeadingText("bebas_neue.ttf")
    img = f.render(text="Hello, World!", split_size=96)
    img.show()
