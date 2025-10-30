import binascii
from uuid import UUID


class FunnyPackets:
    STATUS: bytes = b"\x5a\x02"
    HANDSHAKE_0A: bytes = b"\x5a\x0a"
    HANDSHAKE_0B: bytes = b"\x5a\x0b"
    PRINTING_PAUSED: bytes = b"\x5a\x08"
    PRINTING_FINISHED: bytes = b"\x5a\x06"
    LOST_PACKET: bytes = b"\x5a\x05"
    HARDWARE_INFO: bytes = b"\x5a\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"

    STATIC_CHALLENGE: bytes = b"\x00" * 10
    BLANK_LINE: bytes = b"\x00" * 48

    WRITE = UUID("0000ffe1-0000-1000-8000-00805f9b34fb")
    READ = UUID("0000ffe2-0000-1000-8000-00805f9b34fb")

    DELAY: float = 0.02

    @staticmethod
    def density(density: int):
        """Printing density (darkness). 0-7."""
        if not 0 <= density <= 7:
            raise ValueError("Density must be in range 0..7")
        return b"\x5a\x0c" + density.to_bytes(1, "big")

    @staticmethod
    def random_0a():
        """Handshake phase 1 - challenge

        Handshake involves challenge-response authentication before
        anything could be printed.

        1. The client sends client-challenge "5a 0a" packet with 10 random bytes
        2. The printer returns 10 bytes of printer-challenge in "5a 0a" reply packet
        3. The client sends challenge-response in "5a 0b" packet

        However, the protocol is completely flawed, which allows to
        just hard-code static client-challenge and generate final response
        from the MAC address only, without even using printer-challenge data.
        This is most likely not a print-challenge at all, but a garbage RAM
        data due to incorrect packet length.

        The protocol operates on byte-basis (each challenge byte corresponds to
        other response byte, regardless of other bytes or the position), that's
        why we use only the first byte out of 10, and multiply it.
        """
        return b"\x5a\x0a" + FunnyPackets.STATIC_CHALLENGE

    @staticmethod
    def reply_0b(bdaddr):
        """Handshake phase 2 - response

        The second step of pointless authentication.
        """

        def crc16_xmodem(data):
            """CRC16-XMODEM implementation matching the native application"""
            crc = 0
            for byte in data:
                for i in range(8):
                    bit = (byte >> (7 - i)) & 1
                    c15 = (crc >> 15) & 1
                    crc <<= 1
                    crc &= 0xFFFF
                    if c15 ^ bit:
                        crc ^= 0x1021
            return crc

        mac_hex = bdaddr.replace(":", "")
        payload_bytes = FunnyPackets.STATIC_CHALLENGE[0:1] + binascii.unhexlify(mac_hex)
        response = (crc16_xmodem(payload_bytes) >> 8) & 0xFF

        return b"\x5a\x0b" + bytes([response]) * 10

    @staticmethod
    def start_print(num_lines: int):
        return FunnyPackets.print_event(num_lines, end=False)

    @staticmethod
    def end_print(num_lines: int):
        return FunnyPackets.print_event(num_lines, end=True)

    @staticmethod
    def print_event(num_lines, end=False):
        """
        Print Start/Stop packets.
        num_lines are "funny" lines, i.e. two raster lines combined.
        """
        return b"\x5a\x04" + num_lines.to_bytes(2, "big") + end.to_bytes(2, "little")

    @staticmethod
    def print_line(line_no, data):
        """Raster data"""
        return b"\x55" + line_no.to_bytes(2, "big") + data + b"\x00"
