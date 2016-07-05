
from coders import UnsignedInteger, Boolean, BIG
from containers import Record, Choice


class Packet(Record):
    packet_id = UnsignedInteger(default=0, byte_order=BIG, width=4)
    size = UnsignedInteger(default=0, byte_order=BIG, width=2)
    request_ack = Boolean(default=True)

    order = ("packet_id", "size", "request_ack")


class GetStatus(Record):
    order = ()


class Upgrade(Record):
    order = ()


class Reset(Record):
    order = ()


class GeneralCommands(Choice):
    variants = {
        0x00: GetStatus,
        0x01: Upgrade,
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
