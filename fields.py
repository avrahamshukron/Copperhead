import binascii
import functools

import struct

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

    STANDARD_WIDTHS = {1: "b", 2: "h", 4: "i", 8: "d"}
    ENDIAN = {BIG: ">", LITTLE: "<"}

    def __init__(self, initial_value=0,
                 width=4, min_value=None,
                 max_value=None, **kwargs):
        if width < 1:
            raise ValueError("Invalid width: %s. Must be at least 1" % (width,))

        super(SignedIntegerField, self).__init__(initial_value, **kwargs)
        self.validators.append(RangeValidator(min_value, max_value))
        self.width = width
        width_symbol = self.STANDARD_WIDTHS.get(width)

        # Fallback encoding. Can be optimized with width is standard integer.
        self._encode_func = self._encode_using_binascii

        self.format = ("%s%s" % (self.ENDIAN[self.byte_order], width_symbol)
                       if width_symbol else None)
        if self.format is not None:
            # Width is standard. Better encoding available.
            self._encode_func = self._encode_using_struct

        # Fallback decoding. Can be optimized if on Python 3.2 and above, or if
        # width is standard integer width.
        self._decode_func = self._decode_manually

        from_bytes = getattr(int, "from_bytes", None)
        if from_bytes is not None:
            # Python 3.2 and above. Best option. Best performance
            self._decode_func = functools.partial(
                from_bytes, byteorder=self.byte_order, signed=True)
        elif self.format is not None:
            # Utilize the struct module.
            self._decode_func = self._decode_using_struct

    def _encode(self):
        # Not setting _encode = _encode_func so that subclasses could override.
        return self._encode_func()

    def _encode_using_struct(self):
        return struct.pack(self.format, self.value)

    def _encode_using_binascii(self):
        as_hex = hex(self.value)[2:]
        length = len(as_hex)
        even_length = as_hex.rjust(length + length % 2, "0")
        encoded = binascii.unhexlify(even_length)
        if self.byte_order == LITTLE:
            encoded = encoded[::-1]
        return encoded

    def _decode(self, byte_buf):
        if len(byte_buf) < self.width:
            raise ValueError("Cannot decode - not enough data supplied")

        mine = byte_buf[:self.width]
        rest = byte_buf[self.width:]
        self.value = self._decode_func(mine)
        return rest

    def _decode_using_struct(self, as_bytes):
        return struct.unpack(self.format, as_bytes)[0]

    def _decode_manually(self, as_bytes):
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
        self._decode_func = lambda s: False if s == "\x00" else True

    def _encode(self):
        # Optimized since we only have two possible values
        return "\x01" if self.value else "\x00"
