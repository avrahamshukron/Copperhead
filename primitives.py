import struct

from coders import Coder
from validators import MembershipValidator, RangeValidator


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
        self.validators = []

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

        # Add class-wise bounds validator
        self.validators.append(RangeValidator(self.min, self.max))
        # Add user bounds validator
        self.validators.append(RangeValidator(min_value, max_value))

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
        for validator in self.validators:
            validator.validate(value)
        return True

    def default_value(self):
        return self.default

    def encode(self, value, stream):
        stream.write(self._encode(value))

    def _encode(self, value):
        if self.validate(value):
            return self.struct.pack(value)

    def _decode(self, buf):
        value = self._decode_func(buf[:self.width])
        if self.validate(value):
            remainder = buf[self.width:]
            return value, remainder

    def decode(self, stream):
        mine = stream.read(self.width)
        if not len or len(mine) < self.width:
            raise ValueError("Cannot decode - reached end of data")

        return self._decode(mine)[0]  # Return only the value.

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

    def _encode(self, value):
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

    def __init__(self, values, width=DEFAULT_WIDTH, **kwargs):
        """
        Creates a new enum from a given dict of values.

        :param values: A dict mapping `name -> value`
        :type values: dict
        """
        super(Enum, self).__init__(width=width, **kwargs)
        self.values = Holder(**values)
        self.validators.append(MembershipValidator(self.values))


__all__ = (UnsignedInteger.__name__, SignedInteger.__name__, Boolean.__name__,
           Enum.__name__)
