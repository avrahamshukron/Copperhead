from protopy.containers import Record, Choice, Member, BitMaskedInteger, BitMask
from protopy.primitives import UnsignedInteger, Boolean, String


class GetStatus(Record):
    is_active = Member(Boolean())
    uptime = Member(UnsignedInteger(width=4))


class Reset(Record):
    pass


class General(Choice):
    variants = {
        0xfa: GetStatus,
        0x02: Reset
    }


class Command(Choice):
    tag_width = 2

    class Upgrade(Record):
        path = Member(String(max_length=1024))

    class Dummy(Record):
        counter_size = Member(UnsignedInteger(width=4))

    variants = {
        0x01: Upgrade,
        0x12: Dummy
    }


class Flags(BitMaskedInteger):
    width = 1
    packet_type = BitMask(0b11000000)
    protocol = BitMask(0b00110000)
    request_ack = BitMask(0b00001000)
    field_d = BitMask(0b00000111)


class Header(Record):
    barker = Member(UnsignedInteger(default=0xcafebeef))
    size = Member(UnsignedInteger(width=2))
    inverted_size = Member(UnsignedInteger(width=2))


class Packet(Record):
    header = Member(Header)
    payload = Member(Command)
    crc = Member(UnsignedInteger())
