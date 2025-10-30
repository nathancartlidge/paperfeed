import asyncio
import logging
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
from bleak import BleakClient, BleakGATTCharacteristic

from paperfeed.driver.constants import FunnyPackets


class Packet(NamedTuple):
    header: bytes
    body: bytes


@dataclass
class PrinterStatus:
    battery: int
    battery_low: bool
    battery_charging: bool
    overheat: bool
    paper: bool


@dataclass(frozen=True)
class Image:
    density: int
    data: np.ndarray[np.bool]

    def __post_init__(self):
        assert self.data.shape[0] == 384, "invalid width (should be 384)"

    @property
    def funny_height(self):
        return round(self.data.shape[1] / 2)

    @property
    def start_messages(self) -> list[bytearray]:
        return [
            FunnyPackets.density(self.density),
            FunnyPackets.start_print(num_lines=self.funny_height),
        ]

    @property
    def end_messages(self) -> list[bytearray]:
        return [FunnyPackets.end_print(num_lines=self.funny_height)]

    @property
    def line_packets(self) -> list[bytearray]:
        width, height = self.data.shape
        assert width == 384, "invalid width (should be 384)"

        lines = []
        for line in self.data:
            lines.append(np.packbits(line))

        if len(lines) % 2 == 1:
            lines.append(FunnyPackets.BLANK_LINE)

        funny_lines = [
            FunnyPackets.print_line(i, top + bot)
            for i, (top, bot) in enumerate(zip(lines[::2], lines[1::2]))
        ]
        assert len(funny_lines) == self.funny_height

        return funny_lines


class Driver(FunnyPackets):
    def __init__(self, address: str):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._address: str = address

        self._client: BleakClient | None = None
        self._messages: asyncio.Queue[Packet] = asyncio.Queue()
        self._status: PrinterStatus | None = None

    @property
    def address(self) -> str:
        return self._address

    @property
    def status(self) -> PrinterStatus | None:
        return self._status

    async def __aenter__(self):
        self._client = BleakClient(self.address)
        await self._client.connect()

        if await self._handshake():
            return self
        raise RuntimeError("Handshake failed")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client is not None:
            await self._client.disconnect()

        self._messages.empty()
        self._status = None
        self._client = None

    async def _handshake(self) -> bool:
        assert self._client is not None, "No client (call inside context mgr)"

        self._logger.info("Subscribing to 'notify' channel")
        await self._client.start_notify(self.READ, self._read_callback)

        self._logger.info("Starting handshake")
        await self._write(self.HARDWARE_INFO)

        await self._write(self.random_0a())
        response = await self._read()

        if response.header != self.HANDSHAKE_0A:
            return False

        await self._write(self.reply_0b(self._address))
        response = await self._read()

        if response.header != self.HANDSHAKE_0B or response.body[0] != 0x01:
            return False

        return True

    async def _read_callback(self, sender: BleakGATTCharacteristic, data: bytearray):
        header = data[0:2]
        body = data[2:]
        await self._messages.put(Packet(header, body))

        if header == self.STATUS:
            # data structure:
            #  0 | battery_level
            #  1 | no_paper
            #  2 | charging
            #  3 | overheat
            #  4 | lowVoltage
            #  5 | density
            self._status = PrinterStatus(
                battery=body[0],
                paper=not body[1],
                battery_charging=bool(body[2]),
                overheat=bool(body[3]),
                battery_low=bool(body[4]),
            )
            self._logger.info("Status report: %s", self._status)
            if body[3]:
                self._logger.warning("Printer Overheating!")
        elif header == self.LOST_PACKET:
            self._logger.warning("Lost packet")

    async def _write(self, data):
        assert self._client is not None, "No client (call inside context mgr)"
        return await self._client.write_gatt_char(self.WRITE, data, response=False)

    async def _read(self) -> Packet:
        return await self._messages.get()

    async def print(self, image: Image) -> bool:
        assert self._client is not None, "No client (call inside context mgr)"

        for command in image.start_messages:
            await self._write(command)
            await asyncio.sleep(self.DELAY)

        lines = image.line_packets
        next_line = 0
        waiting_for_finish_count = 0
        print_success = False

        while True:
            if not self._messages.empty():
                msg = await self._messages.get()
                if msg.header == self.LOST_PACKET:
                    # retransmit from line n-1
                    last_seen = int.from_bytes(msg.body[0:2], "big")
                    next_line = last_seen - 1
                    continue
                elif msg.header == self.PRINTING_PAUSED:
                    # todo: should we check status here?
                    # "more to come" signal; wait for more
                    while self._messages.empty():
                        await asyncio.sleep(self.DELAY)
                    continue
                elif msg.header == self.PRINTING_FINISHED:
                    # we have finished printing!
                    print_success = True

            if next_line < len(lines):
                line = lines[next_line]
                await self._write(line)
                next_line += 1
            else:
                waiting_for_finish_count += 1

            await asyncio.sleep(self.DELAY)
            if waiting_for_finish_count >= 100:
                # blocked for over 2 seconds waiting for a packet
                print_success = False
                break

        for command in image.end_messages:
            await self._write(command)
            await asyncio.sleep(self.DELAY)

        return print_success
