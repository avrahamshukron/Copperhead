import struct

from coders import Coder


class ByteOrder(object):
    LITTLE = "little"
    BIG = "big"
    MSB_FIRST = BIG
    LSB_FIRST = LITTLE


class UnsignedInteger(Coder):

    DEFAULT_BYTE_ORDER = ByteOrder.MSB_FIRST
    STANDARD_WIDTHS = {1: "B", 2: "H", 4: "I", 8: "Q"}
    ENDIAN = {ByteOrder.MSB_FIRST: ">", ByteOrder.LSB_FIRST: "<"}
    DEFAULT_WIDTH = 4
    SIGNED = False

    @classmethod
    def get_bounds(cls, width):
        return 0, 2 ** (8 * width) - 1

    def __init__(self, default=0,
                 width=DEFAULT_WIDTH, min_value=None,
                 max_value=None, byte_order=DEFAULT_BYTE_ORDER):

        if width not in self.STANDARD_WIDTHS:
            raise ValueError("Invalid width: %s. Supported widths are %s" %
                             (width, sorted(self.STANDARD_WIDTHS.keys())))

        self.default = default
        self.byte_order = byte_order
        self.width = width
        self.min, self.max = self.get_bounds(self.width)

        if min_value is not None and min_value > self.min:
            self.min = min_value

        if max_value is not None and max_value < self.max:
            self.max = max_value

        # Fallback decoding. Can be optimized if on Python 3.2 and above
        self._decode_func = self._decode_using_struct

        width_symbol = self.STANDARD_WIDTHS.get(self.width)
        self.struct = struct.Struct(
            "%s%s" % (self.ENDIAN[self.byte_order], width_symbol))

        from_bytes = getattr(int, "from_bytes", None)
        if from_bytes is not None:
            # Python 3.2 and above. Best option. Best performance
            self._decode_func = self._decode_using_int

    def validate(self, value):
        if self.min <= value <= self.max:
            return True

        raise ValueError("%s is out of [%s, %s]" % (value, self.min, self.max))

    def default_value(self):
        return self.default

    def write_to(self, value, stream):
        encoded = self.encode(value)
        stream.write(encoded)
        return len(encoded)

    def encode(self, value):
        if self.validate(value):
            return self.struct.pack(value)

    def decode(self, buf):
        value = self._decode_func(buf[:self.width])
        if self.validate(value):
            remainder = buf[self.width:]
            return value, remainder

    def read_from(self, stream):
        mine = stream.read(self.width)
        if not len or len(mine) < self.width:
            raise ValueError("Cannot decode - reached end of data")
        decoded, _ = self.decode(mine)
        return decoded

    def _decode_using_int(self, as_bytes):
        # noinspection PyUnresolvedReferences
        return int.from_bytes(as_bytes, byteorder=self.byte_order,
                              signed=self.SIGNED)

    def _decode_using_struct(self, as_bytes):
        return self.struct.unpack(as_bytes)[0]


class SignedInteger(UnsignedInteger):

    STANDARD_WIDTHS = {1: "b", 2: "h", 4: "i", 8: "q"}
    SIGNED = True

    @classmethod
    def get_bounds(cls, width):
        value_bits = 8 * width - 1  # -1 for the sign bit
        return -2 ** value_bits, 2 ** value_bits - 1


class Boolean(UnsignedInteger):

    def __init__(self, default=False, **kwargs):
        # BooleanField is a 1-byte integer
        super(Boolean, self).__init__(default, width=1, **kwargs)
        self._decode_func = self._decode_bool

    def encode(self, value):
        # Optimized since we only have two possible values
        return "\x01" if value else "\x00"

    @staticmethod
    def _decode_bool(as_bytes):
        return False if as_bytes == "\x00" else True


class Holder(object):
    def __init__(self, **kwargs):
        self.values = set(kwargs.values())
        for name, value in kwargs.iteritems():
            setattr(self, name, value)


class Enum(UnsignedInteger):

    DEFAULT_WIDTH = 1

    def __init__(self, members, width=DEFAULT_WIDTH, **kwargs):
        """
        Creates a new enum from a given dict of values.

        :param members: A dict mapping `name -> value`
        :type members: dict
        """
        default = kwargs.pop("default", None)
        if default is None:
            if len(members) > 0:
                # The default will be the lowest value in the enum's members
                default = sorted(members.keys())[0]
        elif default not in members.values:
            raise ValueError("Default value %s is not one of %s" %
                             (default, members,))

        super(Enum, self).__init__(width=width, default=default, **kwargs)
        self.members = Holder(**members)

    def validate(self, value):
        if value in self.members.values:
            return True
        raise ValueError("%s not a member of %s", (value, self.members))


class Sequence(Coder):

    def __init__(self, element_coder, length_coder=None):
        """
        Initialize new Sequence.
        """
        self.length_coder = length_coder
        self.element_coder = element_coder

    def default_value(self):
        return []

    def write_to(self, value, stream):
        written = self._write_length(stream, value)
        written += self._write_elements(stream, value)
        return written

    def _write_elements(self, stream, value):
        written = 0
        for element in value:
            written += self.element_coder.write_to(element, stream)
        return written

    def _write_length(self, stream, value):
        length = len(value)
        written = 0
        if self.length_coder is not None:
            written = self.length_coder.write_to(length, stream)
        return written

    def _read_length(self, stream):
        if self.length_coder is None:
            return -1
        return self.length_coder.read_from(stream)

    def read_from(self, stream):
        count = self._read_length(stream)
        return self._read_elements(count, stream)

    def _read_elements(self, count, stream):
        if count < 0:
            return self._read_countless(stream)
        return [self.element_coder.read_from(stream) for _ in xrange(count)]

    def _read_countless(self, stream):
        # If you try to decode an element from a depleted stream, you'll get a
        # ValueError.
        # This means we cannot distinguish between EOF and a real decode error.
        # Because of that we cannot decode countless elements from a stream,
        # since it is bound to fail with ValueError somewhere along the way.
        data = stream.read()
        items = []
        while data:
            item, data = self.element_coder.decode(data)
            items.append(item)
        return items

    def validate(self, elements):
        if self.length_coder is not None:
            self.length_coder.validate(len(elements))

        for elem in elements:
            self.element_coder.validate(elem)

        return True


class String(Sequence):

    def __init__(self, length_coder=None):
        super(String, self).__init__(None, length_coder)

    def _write_elements(self, stream, value):
        stream.write(value)

    def _read_elements(self, count, stream):
        return stream.read(count)

    def default_value(self):
        return ""

    def validate(self, value):
        if isinstance(value, str):
            return True
        raise ValueError("%s is not a string" % (str(value),))


__all__ = (UnsignedInteger.__name__, SignedInteger.__name__, Boolean.__name__,
           Enum.__name__, Sequence.__name__, String.__name__)
