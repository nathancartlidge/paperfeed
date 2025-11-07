from PIL import Image


def to_1_bit(img: Image.Image, threshold: int = 128, use_dithering: bool = False):
    if use_dithering:
        img_mono = img.convert("1")  # Floyd-Steinberg dithering
    else:
        img_mono = img.point(lambda x: 0 if x < threshold else 255, mode="1")

    return img_mono
