from unittest import TestCase
from primitives import UnsignedInteger, Boolean, ByteOrder
from containers import Record, Choice


class RecordTest(TestCase):

    class Packet(Record):
        packet_id = UnsignedInteger(
            default=0, byte_order=ByteOrder.BIG, width=4)
        size = UnsignedInteger(default=0, byte_order=ByteOrder.BIG, width=2)
        request_ack = Boolean(default=True)

        order = ("packet_id", "size", "request_ack")

    cases = (
        (dict(packet_id=0, size=0, request_ack=False),
         "\x00\x00\x00\x00\x00\x00\x00"),
        (dict(
            packet_id=Packet.packet_id.max,
            size=Packet.size.max,
            request_ack=True
        ), "\xff\xff\xff\xff\xff\xff\x01"),
        (dict(packet_id=0x12345678, size=0x9876, request_ack=False),
         "\x12\x34\x56\x78\x98\x76\x00"),
    )

    def test_creation(self):
        p = self.Packet(packet_id=5, size=17, request_ack=True)
        self.failUnlessEqual(p.packet_id, 5)
        self.failUnlessEqual(p.size, 17)
        self.failUnlessEqual(p.request_ack, True)

    def test_encoding(self):
        for values, expected in self.cases:
            p = self.Packet(**values)
            buf = self.Packet._encode(p)
            self.failUnlessEqual(buf, expected)

    def test_decoding(self):
        for values, expected in self.cases:
            p, _ = self.Packet._decode(expected)
            for name, value in values.iteritems():
                self.failUnlessEqual(value, getattr(p, name))


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
