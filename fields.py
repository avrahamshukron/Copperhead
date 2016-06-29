import struct

from validators import RangeValidator, MembershipValidator

LITTLE = "little"
BIG = "big"
MSB_FIRST = BIG
LSB_FIRST = LITTLE


class Serializable(object):

    def encode(self):
        """
        Encode this object as a sequence of binary bytes
        :return: This object encoded.
        """
        raise NotImplementedError("Abstract class")

    def decode(self, buf):
        """
        Decode the value of this object from a sequence of bytes.

        :param buf: A binary byte sequence
        :return: The remainder of the buffer after consuming the data used by
            this object.
        """
        raise NotImplementedError("Abstract class")


class Field(object):
    """
    Base class representing Field that can be decoded/encoded
    """
    # The creation_counter tracks each time a Field instance is created.
    # Used to retain order, which is important for encoding/decoding of Record
    # objects that define several fields.
    creation_counter = 0

    def __init__(self, **kwargs):
        self.validators = []
        self.creation_counter = Field.creation_counter
        Field.creation_counter += 1

    def get_default(self):
        raise NotImplementedError("Abstract class")

    def validate(self, value):
        for validator in self.validators:
            validator.validate(value)
        return True

    def encode(self, value, out_buf):
        """
        Encode ``value`` as a bytes into ``out_buf``.

        :param value: A value suitable for this object.
        :param out_buf: A file-like object that has the ``write`` method.

        :return: True if the operation succeeded.
        :raise ValueError: If the value could not be encoded.
        """
        if self.validate(value):
            return self._encode(value, out_buf)

    def _encode(self, value, out_buf):
        """
        Perform the actual encoding. Subclasses must implement.
        """
        raise NotImplementedError("Subclasses must implement")

    def decode(self, in_buf):
        """
        Decode a value from a ``in_buf``.

        :param in_buf: A file-like object that has the ``read(int)`` method.

        :return: The the value that was decoded.
        :raise ValueError: If the data could not be decoded.
        """
        value = self._decode(in_buf)
        if self.validate(value):
            return value

    def _decode(self, byte_buf):
        """
        Does the actual decoding and sets the ``value`` attribute.
        Subclasses must implement.

        :return: The remaining buffer, without the data which was decoded.
        """
        raise NotImplementedError("Subclasses must implement")


class UnsignedIntegerField(Field):

    DEFAULT_BYTE_ORDER = MSB_FIRST
    STANDARD_WIDTHS = {1: "B", 2: "H", 4: "I", 8: "Q"}
    ENDIAN = {MSB_FIRST: ">", LSB_FIRST: "<"}
    DEFAULT_WIDTH = 4
    SIGNED = False

    @classmethod
    def get_bounds(cls, width):
        return 0, 2 ** (8 * width) - 1

    def __init__(self, default=0,
                 width=DEFAULT_WIDTH, min_value=None,
                 max_value=None, byte_order=DEFAULT_BYTE_ORDER, **kwargs):
        super(UnsignedIntegerField, self).__init__(**kwargs)

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

    def get_default(self):
        return self.default

    def _encode(self, value, out_buf):
        out_buf.write(self.struct.pack(value))
        return True

    def _decode(self, in_buf):
        mine = in_buf.read(self.width)
        if not len or len(mine) < self.width:
            raise ValueError("Cannot decode - reached end of data")

        return self._decode_func(mine)

    def _decode_using_int(self, as_bytes):
        # noinspection PyUnresolvedReferences
        return int.from_bytes(as_bytes, byteorder=self.byte_order,
                              signed=self.SIGNED)

    def _decode_using_struct(self, as_bytes):
        return self.struct.unpack(as_bytes)[0]


class SignedIntegerField(UnsignedIntegerField):

    STANDARD_WIDTHS = {1: "b", 2: "h", 4: "i", 8: "q"}
    SIGNED = True

    @classmethod
    def get_bounds(cls, width):
        value_bits = 8 * width - 1  # -1 for the sign bit
        return -2 ** value_bits, 2 ** value_bits - 1


class BooleanField(UnsignedIntegerField):

    def __init__(self, default=False, **kwargs):
        # BooleanField is a 1-byte integer
        super(BooleanField, self).__init__(default, width=1, **kwargs)

    def _encode(self, value, out_buf):
        # Optimized since we only have two possible values
        out_buf.write("\x01" if value else "\x00")

    @staticmethod
    def _decode_func(as_bytes):
        return False if as_bytes == "\x00" else True


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

    def __init__(self, values, width=DEFAULT_WIDTH, **kwargs):
        super(EnumField, self).__init__(width=width, **kwargs)
        self.values = Enum(values)
        self.validators.append(MembershipValidator(self.values))
