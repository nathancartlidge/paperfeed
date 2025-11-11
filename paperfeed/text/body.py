import logging
from pathlib import Path

from PIL import Image
from PIL.ImageFont import FreeTypeFont

from paperfeed.text.constants import LINE_WIDTH
from paperfeed.text.text import Text


class BodyText(Text):
    def __init__(self, file: Path | str, target_width: int = LINE_WIDTH):
        super().__init__(file=file)
        self._target_width = target_width

    def render(self, text: str, font_size: int | float = 24) -> Image.Image:
        font = self.at_size(font_size)
        lines = self.split_lines(text=text, font=font)
        self._logger.info("Made %d lines", len(lines))

        total_height = font_size * len(lines)
        image = Image.new("1", (self._target_width, total_height), 0)

        offset_y = 0
        for line_img, offset_x in lines:
            image.paste(line_img, (offset_x, offset_y))
            offset_y += font_size
        return image

    def split_lines(
        self, text: str, font: FreeTypeFont
    ) -> list[tuple[Image.Image, int]]:
        """for now, a naive algorithm"""
        text = (
            text.split()
        )  # note: issues with multiple whitespace and ignoring newlines
        lines = []
        current_line = []
        current_line_image: Image.Image | None = None
        for word in text:
            current_line.append(word)
            line_text = " ".join(current_line)
            bbox_est = font.getbbox(line_text)
            img_height = 2 + round(bbox_est[3] - bbox_est[1])
            too_wide = bbox_est[2] - bbox_est[0] > self._target_width

            if too_wide and current_line_image is not None:
                bbox = current_line_image.getbbox()
                lines.append((current_line_image, -bbox[0]))
                current_line = [word]
                current_line_image = None
            else:
                line_image = self._render_text(
                    font, line_text, width=self._target_width + 20, height=img_height
                )
                current_line_image = line_image

        if current_line:
            if current_line_image is None:
                line_text = " ".join(current_line)
                current_line_image = self._render_text(
                    font, line_text, width=self._target_width + 20
                )

            bbox = current_line_image.getbbox()
            lines.append((current_line_image, -bbox[0]))

        return lines


if __name__ == "__main__":
    # Usage
    logging.basicConfig(level=logging.INFO)
    f = BodyText("roboto.ttf")
    img = f.render(
        text="""
        According to all known laws of aviation, there is no way a bee should be able to fly.
        Its wings are too small to get its fat little body off the ground.
        The bee, of course, flies anyway because bees don't care what humans think is impossible.
        Yellow, black. Yellow, black. Yellow, black. Yellow, black.
        Ooh, black and yellow!
        Let's shake it up a little.
    """,
        font_size=24,
    )
    img.show()
