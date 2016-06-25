import binascii
import struct

from validators import RangeValidator, MembershipValidator

LITTLE = "little"
BIG = "big"


class Field(object):
    """
    Base class representing Field that can be decoded/encoded
    """

    DEFAULT_BYTE_ORDER = BIG

    def __init__(self, initial_value, byte_order=DEFAULT_BYTE_ORDER):
        self.value = initial_value
        self.byte_order = byte_order
        self.validators = []

    def validate(self, value):
        for validator in self.validators:
            validator.validate(value)
        return True

    def encode(self):
        """
        Encode this object as a byte string.

        :return: The encoded bytes representing the ``value`` attribute.
        :raise ValueError: If the value cannot be encoded.
        """
        if self.validate(self.value):
            return self._encode()

    def _encode(self):
        """
        Perform the actual encoding. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement")

    def decode(self, byte_buf):
        """
        Decode an value from a byte string, and sets it as its own.

        :param byte_buf: A bytes-like object or an iterable producing bytes.

        :return: The remaining buffer, without the data which was decoded.
        :raise ValueError: If the data could not be decoded.
        """
        rest = self._decode(byte_buf)
        if self.validate(self.value):
            return rest

    def _decode(self, byte_buf):
        """
        Does the actual decoding and sets the ``value`` attribute.
        Subclasses must implement.

        :return: The remaining buffer, without the data which was decoded.
        """
        raise NotImplementedError("Subclasses must implement")


class UnsignedIntegerField(Field):

    STANDARD_WIDTHS = {1: "B", 2: "H", 4: "I", 8: "Q"}
    ENDIAN = {BIG: ">", LITTLE: "<"}
    DEFAULT_WIDTH = 4

    @classmethod
    def get_bounds(cls, width):
        return 0, 2 ** (8 * width) - 1

    def __init__(self, initial_value=0,
                 width=DEFAULT_WIDTH, min_value=None,
                 max_value=None, **kwargs):
        if width not in self.STANDARD_WIDTHS:
            raise ValueError("Invalid width: %s. Supported widths are %s" %
                             (width, sorted(self.STANDARD_WIDTHS.keys())))

        super(UnsignedIntegerField, self).__init__(initial_value, **kwargs)
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

    def _encode(self):
        return self.struct.pack(self.value)

    def _decode(self, byte_buf):
        if len(byte_buf) < self.width:
            raise ValueError("Cannot decode - not enough data supplied")

        mine = byte_buf[:self.width]
        rest = byte_buf[self.width:]
        self.value = self._decode_func(mine)
        return rest

    def _decode_using_int(self, as_bytes):
        # noinspection PyUnresolvedReferences
        return int.from_bytes(as_bytes, byteorder=self.byte_order, signed=False)

    def _decode_using_struct(self, as_bytes):
        return self.struct.unpack(as_bytes)[0]


class SignedIntegerField(UnsignedIntegerField):

    STANDARD_WIDTHS = {1: "b", 2: "h", 4: "i", 8: "q"}
    ENDIAN = {BIG: ">", LITTLE: "<"}

    @classmethod
    def get_bounds(cls, width):
        value_bits = 8 * width - 1  # -1 for the sign bit
        return -2 ** value_bits, 2 ** value_bits - 1


class BooleanField(UnsignedIntegerField):

    def __init__(self, initial_value=False):
        # BooleanField is a 1-byte integer
        super(BooleanField, self).__init__(initial_value, width=1)
        self._decode_func = lambda s: False if s == "\x00" else True

    def _encode(self):
        # Optimized since we only have two possible values
        return "\x01" if self.value else "\x00"


class Enum(object):
    def __init__(self, values):
        """
        Creates a new enum from a given dict of values.

        :param values: A dict mapping ``name -> value``
        :type values: dict
        """
        self.values = set(values.values())
        for name, value in values.iteritems():
            setattr(self, name, value)


class EnumField(UnsignedIntegerField):

    DEFAULT_WIDTH = 1

    def __init__(self, values, **kwargs):
        width = kwargs.pop("width", self.DEFAULT_WIDTH)
        super(EnumField, self).__init__(width=width, **kwargs)
        self.values = Enum(values)
        self.validators.append(MembershipValidator(self.values))
