import asyncio
import datetime
import logging
from dataclasses import dataclass
from typing import NamedTuple

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from tqdm import tqdm

from paperfeed.driver.constants import FunnyPackets
from paperfeed.driver.image import Image


class Packet(NamedTuple):
    header: bytes
    body: bytes
    timestamp: str


@dataclass
class PrinterStatus:
    battery: int
    battery_low: bool
    battery_charging: bool
    overheat: bool
    paper: bool
    packet: Packet

    @classmethod
    def from_packet(cls, packet: Packet):
        """Parse the packet structure"""
        # data structure:
        #  0 | battery_level
        #  1 | no_paper
        #  2 | charging
        #  3 | overheat
        #  4 | lowVoltage
        #  5 | density
        # weirdly this doesn't seem to be set properly?
        return cls(
            battery=packet.body[0],
            paper=not packet.body[1],
            battery_charging=bool(packet.body[2]),
            overheat=bool(packet.body[3]),
            battery_low=bool(packet.body[4]),
            packet=packet,
        )


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
        assert self._client is not None
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
        self._logger.debug("> Fetching hardware info (ignored)")
        await self._query(self.HARDWARE_INFO)

        self._logger.debug("> Sending A packet")
        challenge_response = await self._query(self.challenge())

        if challenge_response.header != self.HANDSHAKE_0A:
            self._logger.warning("failed handshake challenge: %s", challenge_response)
            return False

        self._logger.debug("> Sending B packet")
        response_response = await self._query(self.response(self._address))

        if (
            response_response.header != self.HANDSHAKE_0B
            or response_response.body[0] != 0x01
        ):
            self._logger.warning("failed handshake response: %s", response_response)
            return False

        return True

    async def _read_callback(self, sender: BleakGATTCharacteristic, data: bytearray):
        header = bytes(data[0:2])
        body = bytes(data[2:])

        now = datetime.datetime.now(tz=datetime.timezone.utc)
        timestamp = now.isoformat()

        packet = Packet(header, body, timestamp)
        await self._messages.put(packet)

        if header == self.STATUS:
            self._logger.debug("New status")
            self._status = PrinterStatus.from_packet(packet)
            if self._status.overheat:
                self._logger.warning("Printer Overheating!")
        elif header == self.LOST_PACKET:
            self._logger.warning("Lost packet")
        elif header == self.PRINTING_PAUSED:
            self._logger.warning("Printing paused")

    async def _write(self, data: bytes | bytearray) -> None:
        assert self._client is not None, "No client (call inside context mgr)"
        return await self._client.write_gatt_char(self.WRITE, data, response=False)

    async def _read(self) -> Packet:
        return await self._messages.get()

    async def _query(self, data: bytes) -> Packet:
        """Combined query and response"""
        # there is a slight race condition here, but we ignore it
        assert self._messages.empty(), "Messages not empty"
        await self._write(data)
        response = await self._messages.get()
        if data[0:2] != response.header:
            raise ValueError("Header mismatch")
        return response

    async def print(self, image: Image, show_progress: bool = True) -> bool:
        assert self._client is not None, "No client (call inside context mgr)"
        lines = image.line_packets

        for command in image.start_messages:
            await self._write(command)
            await asyncio.sleep(self.DELAY)

        next_line = 0
        waiting_for_finish_count = 0
        print_finished = False

        packets = tqdm(
            desc="Sending Packets", total=len(lines), disable=not show_progress
        )
        timeout = None

        while not print_finished:
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
                    print_finished = True

            if next_line < len(lines):
                line = lines[next_line]
                await self._write(line)
                next_line += 1
                packets.update(1)
            else:
                if timeout is None:
                    packets.close()
                    timeout = tqdm(
                        desc="Waiting for Ack", total=len(lines) * 9, leave=False
                    )

                waiting_for_finish_count += 1
                timeout.update(1)

            await asyncio.sleep(self.DELAY)
            if waiting_for_finish_count >= len(lines) * 9:
                # it has taken 10 times as long to print this as we expected
                print_finished = False
                self._logger.info("Failed to finish, aborting")
                break

        if timeout is not None:
            timeout.close()

        for command in image.end_messages:
            await self._write(command)
            await asyncio.sleep(self.DELAY)

        return print_finished
