import struct
from cStringIO import StringIO

import enum34
from coders import Coder


class ByteOrder(str, enum34.Enum):
    MSB_FIRST = "big"
    LSB_FIRST = "little"


class UnsignedInteger(Coder):
    """
    A Coder capable of encoding/decoding unsigned integers.
    """

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
        """
        Initialize a new UnsignedInteger Coder.

        :param default: The default value of this coder.
        :param width: The number of bytes used to represent values by this
            coder. This parameter imposes boundaries on the values that can be
            encoded / decoded. For example, if width = 1, this coder cannot
            encode the value 256, since it cannot be represented by 1 byte.
        :param min_value: A user-defined lower limit for valid values of this
            coder. In order for this value to be considered, it has to be
            greater than the natural lower limit of the coder, which is 0.
        :param max_value: A user-defined upper limit for valid values of this
            coder. In order for this value to be considered, it has to be
            lower than the natural upper limit of the coder, which is
            ``2 ** (8 * width)``
        :param byte_order: The byte-order of this coder. Must be one of
            ByteOrder's values.
        """

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
        mine = buf[:self.width]
        remainder = buf[self.width:]
        if len(mine) != self.width:
            raise ValueError(
                "Premature end of data. Expected %s bytes, got only %s" %
                (self.width, len(mine)))

        value = self._decode_func(mine)
        if self.validate(value):

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

    @classmethod
    def capable_of(cls, max_value, **kwargs):
        """
        Return an instance of this class that is capable of encoding / decoding
        values up to at least ``max_value``

        :param max_value: The maximum value the coder should support.
        :return: An instance of UnsignedInteger capable of encoding / decoding
            values up to at least ``max_value``
        """
        capable_width = None
        for width in sorted(cls.STANDARD_WIDTHS.keys()):
            if 2 ** (8 * width) >= max_value:
                capable_width = width
                break
        if capable_width is None:
            raise ValueError(
                "Cannot create %s coder capable of handling %s. Value is too "
                "large for standard integer widths" % (cls.__name__, max_value)
            )

        return cls(width=capable_width, max_value=max_value, **kwargs)


class SignedInteger(UnsignedInteger):

    STANDARD_WIDTHS = {1: "b", 2: "h", 4: "i", 8: "q"}
    SIGNED = True

    @classmethod
    def get_bounds(cls, width):
        value_bits = 8 * width - 1  # -1 for the sign bit
        return -2 ** value_bits, 2 ** value_bits - 1


class Boolean(UnsignedInteger):
    """
    A Coder capable of encoding/decoding Boolean values.
    """

    def __init__(self, default=False, **kwargs):
        # BooleanField is a 1-byte integer
        super(Boolean, self).__init__(default, width=1, **kwargs)
        self._decode_func = self._decode_bool

    def encode(self, value):
        # Optimized, since we only have two possible values
        return "\x01" if value else "\x00"

    @staticmethod
    def _decode_bool(as_bytes):
        return False if as_bytes == "\x00" else True


class Char(Coder):
    """
    Simple coder for a single character.
    """
    NULL = "\x00"

    def write_to(self, value, stream):
        if len(value) != 1:
            raise ValueError("\"%s\" is not a single character")

        stream.write(value)

    def read_from(self, stream):
        c = stream.read(1)
        if len(c) == 0:
            raise ValueError("Reached end of data while expecting a character")
        return c

    def default_value(self):
        return self.NULL

# Make a single instance of Char as a shared singleton.
Char = Char()


class Sequence(Coder):
    """
    A Sequence is a series of elements of the same type.

    A sequence can be limited by count, or it can be unlimited.
    The limit is represented by a coder, usually UnsignedInteger.
    If a sequence is limited, the number of element is encoded first, with the
    actual element following.
    When decoding a counted sequence, the count is decoded first, and then only
    `count` element are decoded.
    When decoding a countless sequence, the entire buffer/stream is decoded.
    """

    def __init__(self, element_coder, max_length=None,
                 min_length=0, include_length=False, length_width=None):
        """
        Initialize new Sequence.

        :param element_coder: A Coder for the elements in this sequence.
        :param max_length: The maximum number of elements allowed.
        :param min_length: Optional. The minimal number of elements to
            encode / decode. Defaults to 0.
        :param include_length: Whether to encode the number of elements as a
            prefix when encoding the sequence.
        :param length_width: The number of bytes to use when encoding the number
            of elements.
        """
        if max_length is None and length_width is None:
            raise ValueError(
                "You must specify either max_length or length_width. Unbound "
                "sequences are not allowed.")
        self.element_coder = element_coder
        self.max = max_length
        self.min = min_length
        self.include_length = include_length
        self.length_width = length_width
        self.length_coder = UnsignedInteger.capable_of(
            self.max, min_value=self.min)

    def default_value(self):
        return []

    def validate(self, value):
        count = len(value)
        if not self.min <= count <= self.max:
            raise ValueError(
                "Number of elements (%s) is not in [%s, %s]" %
                (count, self.min, self.max))
        return True

    def write_to(self, value, stream):
        if self.validate(value):
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
        if self.include_length:
            written = self.length_coder.write_to(length, stream)
        return written

    def read_from(self, stream):
        count = self._read_length(stream)
        elements = self._read_elements(count, stream)
        if self.validate(elements):
            return elements

    def _read_length(self, stream):
        if not self.include_length:
            return -1
        return self.length_coder.read_from(stream)

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
        while data and len(items) < self.max:
            item, data = self.element_coder.decode(data)
            items.append(item)
        return items


class Array(Sequence):
    """
    Array is a sequence with fixed size.
    """

    def __init__(self, element_coder, size):
        super(Array, self).__init__(
            element_coder=element_coder, min_length=size, max_length=size,
            include_length=False, length_width=None)


class String(Coder):
    """
    Null-terminated character sequence, optionally limited in length.
    """

    def __init__(self, max_length=None):
        """
        Initialize new String coder.

        :param max_length: Upper limit for the length of the string. The NULL
            terminator is taken into this limit, so if the limit is 256 for
            example, the actual string must be at most 255 in length.
        """
        self.max_length = max_length if max_length >= 0 else None

    def default_value(self):
        return ""

    def write_to(self, value, stream):
        ascii = self.asciify(value)
        if Char.NULL in ascii:
            raise ValueError("NULL (\\0) character cannot appear in the string")

        total_length = len(ascii) + 1  # + 1 for null terminator.
        if self.max_length is not None and total_length > self.max_length:
            raise ValueError(
                "String length (%s) is larger than the specified limit (%s). "
                "Be aware that the NULL terminator is also counted towards the"
                " limit" % (total_length, self.max_length))

        stream.write(ascii)
        stream.write(Char.NULL)
        return total_length

    def read_from(self, stream):
        buf = StringIO()
        read = 0
        while True:
            if self.max_length is not None and read >= self.max_length:
                raise ValueError(
                    "Reached maximum length of string (%s) without "
                    "encountering a NULL terminator" % (self.max_length,))

            c = stream.read(1)
            read += 1
            if c == Char.NULL:
                # Don't include the NULL terminator in the result.
                break
            buf.write(c)
        return self.unasciify(buf.getvalue())

    @staticmethod
    def asciify(string):
        """
        Convert a Python string to ascii string.

        :param string: A Python string.
        :return: The ascii encoded version of `string`, if possible.
        :raises ValueError: If `string` cannot be encoded as ascii
        """
        try:
            return string.encode("ascii")
        except UnicodeDecodeError as e:
            raise ValueError(str(e))

    @staticmethod
    def unasciify(string):
        """
        Convert an ascii-encoded string into Python string.

        :param string: An ascii-encoded string.
        :return: The unicode version of `string`, if possible.
        :raises ValueError: If `string` cannot be decoded as ascii
        """
        try:
            return string.decode("ascii")
        except UnicodeDecodeError as e:
            raise ValueError(str(e))


__all__ = (UnsignedInteger.__name__, SignedInteger.__name__, Boolean.__name__,
           Sequence.__name__, String.__name__, ByteOrder.__name__,
           Char.__class__.__name__)
