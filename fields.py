from validators import RangeValidator

LITTLE = "little"
BIG = "big"


class Field(object):
    """
    Base class representing Field that can be decoded/encoded
    """

    validators = []
    DEFAULT_BYTE_ORDER = BIG

    def __init__(self, initial_value, byte_order=DEFAULT_BYTE_ORDER):
        self.value = initial_value
        self.byte_order = byte_order

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


class SignedIntegerField(Field):

    def __init__(self, initial_value=0, width=4, min_value=None,
                 max_value=None):
        super(SignedIntegerField, self).__init__(initial_value)
        self.validators.append(RangeValidator(min_value, max_value))
        self.width = width

    def _encode(self):
        pass

    def _decode(self, byte_buf):
        mine = byte_buf[:self.width]
        rest = byte_buf[self.width:]
        self.value = self._decode(mine)
        return rest

    def _decode_int(self, as_bytes):
        from_bytes = getattr(int, "from_bytes", None)
        if from_bytes is not None:
            # Python > 3.2
            decoded_value = from_bytes(
                as_bytes, byteorder=self.byte_order, signed=True)
        else:
            # Backward compatibility
            decoded_value = self._decode_int_python2(as_bytes)
        return decoded_value

    def _decode_int_python2(self, as_bytes):
        if self.byte_order == LITTLE:
            # Reverse the byte order
            as_bytes = as_bytes[::-1]
        # We can use the int type because it'll return signed int, same as
        # this class
        decoded_value = int(as_bytes.encode("hex"), 16)
        return decoded_value


class BooleanField(SignedIntegerField):

    def __init__(self, initial_value=False):
        # BooleanField is a 1-byte integer
        super(BooleanField, self).__init__(initial_value, width=1)

    def encode(self):
        # Optimized since we only have two possible values
        return "\x01" if self.value else "\x00"

    def decode(self, byte_buf):
        self.value = self._decode(byte_buf[0])
        return byte_buf[1:]
