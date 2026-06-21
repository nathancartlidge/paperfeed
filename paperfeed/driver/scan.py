"""
Adapted from printer-driver-funnyprint

https://github.com/ValdikSS/printer-driver-funnyprint/blob/cc61609c75d903366820fc13384818b55bc87677/src/rastertofunnyprint/rastertofunnyprint.py#L553
"""

import sys
import asyncio
import logging

from bleak import BleakScanner
from bleak.exc import BleakError


async def scan(timeout: int = 1) -> list[tuple[str, str | None]]:
    """
    Scan for Xiqi / Funnyprint devices

    These devices expose generic MAC addresses. However, their "manufacturer
    data" (BLE advertisement data) can be used to identify them reliably.
    """
    logger = logging.getLogger(name="scan")

    try:
        logger.debug("Starting device scan (timeout=%ds)", timeout)
        devices = await BleakScanner.discover(
            timeout=timeout, return_adv=True, cb={"use_bdaddr": True}
        )
    except BleakError as e:
        logger.error(e)
        raise e

    logger.debug("Found %d device(s)", len(devices))
    printers = []
    for device, data in devices.values():
        logger.debug("> Found BLE device '%s' @ %s", device.name, device.address)
        manufacturer = data.manufacturer_data
        if (
            manufacturer.get(213, None) == b"\x00\x00\x0e\xb9"
            and device.name is not None
        ):
            logger.debug(">> Detected as a Xiqi device")
            if sys.platform == "darwin":
                uuid = device.details[0].identifier().UUIDString()
                printers.append((device.address, str(uuid)))
            else:
                printers.append((device.address, None))

    logger.info("Found %d printer(s)", len(printers))
    return printers


def scan_sync():
    logging.basicConfig(level=logging.INFO)
    future = scan()
    return asyncio.run(future)


if __name__ == "__main__":
    scan_sync()
