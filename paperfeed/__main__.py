import asyncio
import logging

from typing import Literal

from paperfeed.driver import Driver, scan, Image
from paperfeed.text import HeadingText


async def run(mode: Literal["text", "image"] = "image", preview: bool = True):
    if mode == "text":
        # make image to print
        font = HeadingText("bebas_neue.ttf")
        bitmap = font.render(text="inversiontesting", split_size=96)
        image = Image(density=4, data=bitmap)
    else:
        image = Image.from_file(
            "../assets/crossword3.png",
            threshold=140,
            use_dithering=False,
            trim_margins=True,
        )

    if preview:
        image.data.show(title="Preview Image")
        continue_print = input("Continue? [Y/n] ")
        if continue_print.lower() in ["n", "no"]:
            return

    # find the printer
    printers = await scan()
    if len(printers) == 0:
        raise RuntimeError("No printer found")
    if len(printers) != 1:
        raise RuntimeError("Too many printers")
    printer = printers[0]

    # connect to the printer and print the image
    async with Driver(printer) as d:
        result = await d.print(image)
        if result:
            print("Successful Print")
        else:
            print("Print Failed")
        print(d.status)


def run_sync():
    logging.basicConfig(level=logging.INFO)
    result = run()
    asyncio.run(result)


if __name__ == "__main__":
    run_sync()
