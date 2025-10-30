"""
Adapted from printer-driver-funnyprint

https://github.com/ValdikSS/printer-driver-funnyprint/blob/cc61609c75d903366820fc13384818b55bc87677/src/rastertofunnyprint/rastertofunnyprint.py#L553
"""

import asyncio
import logging

from bleak import BleakError, BleakScanner

TIMEOUT = 2


async def scan() -> None:
    """
    Scan for Xiqi / Funnyprint devices

    These devices expose generic MAC addresses. However, their "manufacturer
    data" (BLE advertisement data) can be used to identify them reliably.
    """
    logger = logging.getLogger(name="scan")

    try:
        logger.debug("Starting device scan (timeout=%ds)", TIMEOUT)
        devices = await BleakScanner.discover(timeout=TIMEOUT, return_adv=True)
    except BleakError as e:
        logger.error(e)
        raise e

    logger.debug("Found %d device(s)", len(devices))
    printers = 0
    for address, data in devices.values():
        logger.debug("> Found BLE device '%s' @ %s", address.name, address.address)
        manufacturer = data.manufacturer_data
        if (
            manufacturer.get(213, None) == b"\x00\x00\x0e\xb9"
            and address.name is not None
        ):
            logger.debug(">> Detected as a Xiqi device")
            printers += 1

    logger.info("Found %d printer(s)", printers)

def scan_sync():
    logging.basicConfig(level=logging.DEBUG)
    future = scan()
    return asyncio.run(future)


if __name__ == "__main__":
    scan_sync()
