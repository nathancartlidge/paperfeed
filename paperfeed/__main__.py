import asyncio
import logging

import numpy as np

from paperfeed.driver import scan, Driver, Image


async def run():
    printers = await scan()
    if len(printers) == 0:
        raise RuntimeError("No printer found")
    if len(printers) != 1:
        raise RuntimeError("Too many printers")
    printer = printers[0]

    driver = Driver(printer)

    # diagonal lines
    test_pattern = np.zeros((64, 384), dtype=bool)
    test_pattern[2::3, 2::3] = True
    test_pattern[1::3, ::3] = True
    test_pattern[::3, 1::3] = True

    async with driver:
        await driver.print(Image(density=3, data=test_pattern))
        print(driver.status)

def run_sync():
    logging.basicConfig(level=logging.INFO)
    result = run()
    asyncio.run(result)

if __name__ == "__main__":
    run_sync()