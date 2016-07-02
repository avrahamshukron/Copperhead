
from fields import UnsignedIntegerField, BooleanField, BIG
from containers import Record, Choice


class Packet(Record):
    packet_id = UnsignedIntegerField(default=0, byte_order=BIG, width=4)
    size = UnsignedIntegerField(default=0, byte_order=BIG, width=2)
    request_ack = BooleanField(default=True)

    order = ("packet_id", "size", "request_ack")


class GetStatus(Record):
    order = ()


class Upgrade(Record):
    order = ()


class Reset(Record):
    order = ()


class Command(Choice):
    variants = {
        0x00: GetStatus,
        0x01: Upgrade,
        0x02: Reset
    }
