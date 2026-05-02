# for now, just very basic regression tests
from pathlib import Path

import numpy as np
import pytest

from paperfeed.text import Text, HeadingText, BodyText


@pytest.fixture()
def heading_text() -> HeadingText:
    font_file = Path(__file__).parent / ".." / "paperfeed" / "text" / "bebas_neue.ttf"
    assert font_file.exists()
    return HeadingText(font_file)


@pytest.fixture()
def body_text() -> BodyText:
    font_file = Path(__file__).parent / ".." / "paperfeed" / "text" / "roboto.ttf"
    assert font_file.exists()
    return BodyText(font_file)


@pytest.mark.parametrize("filename", ["roboto.ttf", "bebas_neue.ttf"])
def test_load_font(filename):
    font_file = Path(__file__).parent / ".." / "paperfeed" / "text" / filename
    assert font_file.exists(), "font file not downloaded, unable to test"

    # load from a full path
    font_path = Text(font_file)
    font_path_16 = font_path.at_size(16)
    assert font_path_16 is not None

    # load from filename only
    font_filename = Text(filename)
    font_filename_16 = font_filename.at_size(16)
    assert font_filename_16 is not None


@pytest.mark.parametrize("split_size", [48, 64, 96, 128, 256])
def test_make_heading(heading_text: HeadingText, split_size: int):
    img = heading_text.render(
        "Once upon a time, there was a big evil wizard. The end", split_size=split_size
    )
    assert img.width == heading_text._target_width
    assert np.sum(img) > 0


@pytest.mark.parametrize("font_size", [16, 24, 32, 64])
def test_make_body(body_text: BodyText, font_size: int):
    img = body_text.render(
        "Once upon a time, there was a big evil wizard. The end", font_size=font_size
    )
    assert img.width == body_text._target_width
    assert np.sum(img) > 0
