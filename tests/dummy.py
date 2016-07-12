from containers import Record, Choice, Member
from primitives import UnsignedInteger, Boolean, String


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
    class Upgrade(Record):
        path = String()

    variants = {
        0x54: General,
        0x01: Upgrade,
    }


class Header(Record):
    barker = Member(UnsignedInteger(default=0xcafebeef))
    size = Member(UnsignedInteger(width=2))
    inverted_size = Member(UnsignedInteger(width=2))


class Packet(Record):
    header = Member(Header)
    payload = Member(Command)
    crc = Member(UnsignedInteger())
