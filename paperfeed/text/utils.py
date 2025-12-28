from PIL import Image


def to_1_bit(img: Image.Image, threshold: int = 128, use_dithering: bool = False):
    img_grey = img.convert("L")

    if use_dithering:
        img_grey = img_grey.convert("1")  # Floyd-Steinberg dithering
    else:
        img_grey = img_grey.point(lambda x: 255 if x >= threshold else 0, mode="1")

    return img_grey
