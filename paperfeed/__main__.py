import asyncio
import logging

from paperfeed.driver import scan, Driver, Image
from paperfeed.text import HeadingText


async def run(preview: bool = True):
    # make image to print
    font = HeadingText("bebas_neue.ttf")
    bitmap = font.render(text="Hello, World!", split_size=96)
    image = Image(density=4, data=bitmap)

    if preview:
        bitmap.show(title="Preview Image")
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
