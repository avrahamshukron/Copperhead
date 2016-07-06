from containers import Record, Choice
from primitives import UnsignedInteger, ByteOrder


class GetStatus(Record):
    order = ()


class Upgrade(Record):
    order = ()


class Reset(Record):
    order = ()


class GeneralCommands(Choice):
    variants = {
        0x00: GetStatus,
        0x02: Reset
    }


class UpgradeCommands(Choice):
    variants = {
        0x00: Upgrade,
    }


class Command(Choice):
    variants = {
        0x00: GeneralCommands,
        0x01: UpgradeCommands,
    }


class Header(Record):
    barker = UnsignedInteger(
        default=0xcafebeef, byte_order=ByteOrder.BIG, width=4)
    size = UnsignedInteger(default=0, byte_order=ByteOrder.BIG, width=2)
    inverted_size = size
    order = ("barker", "size", "inverted_size")


class Packet(Record):
    header = Header
    payload = Command
    crc = UnsignedInteger(width=4, byte_order=ByteOrder.BIG)
    order = ("header", "payload", "crc")
