from cStringIO import StringIO


class Encoder(object):

    def write_to(self, value, stream):
        """
        Encode a value into a stream.

        :param value: The value to encode.
        :param stream: A writeable file-like object.
        :return: The number of bytes written.
        :raise ValueError: If `value` could not be encoded.
        """
        raise NotImplementedError("Subclasses must implement")

    def encode(self, value):
        """
        Encode the given value as a sequence of bytes.

        :param value: The value to encode.
        :return: A sequence of bytes representing `value`
        :raise ValueError: If `value` could not be encoded.
        """
        # Naive implementation. Subclasses are encourage to override if it
        # makes more sense.
        stream = StringIO()
        self.write_to(value, stream)
        return stream.getvalue()


class Decoder(object):

    def read_from(self, stream):
        """
        Decode a value from a stream.

        This function will read from the stream the required number of bytes to
        decode a value. When this method returns, the position of the file will
        be after the data that has been decoded.

        :param stream: A readable file-like object.
        :return: The value decoded.
        :raise ValueError: If the buffer cannot be decoded.
        :return: An object decoded from the bytes read.
        """
        raise NotImplementedError("Subclasses must implement")

    def decode(self, buf):
        """
        Decode a value from a buffer.

        :param buf: A sequence of bytes.
        :return: (value, remainder) A tuple of the value decoded and the
            remainder of the buffer.
        :raise ValueError: If the buffer cannot be decoded.
        """
        # Naive implementation. Subclasses are encourage to override if it
        # makes more sense.
        stream = StringIO(buf)
        value = self.read_from(stream)
        remainder = stream.read()
        return value, remainder


# noinspection PyAbstractClass
class Coder(Encoder, Decoder):
    """
    Aggregates both Encoder and Decoder interfaces.
    """

    def default_value(self):
        """
        Return the value that is considered "default" or "empty" for this type.
         For example, this might be 0 for Integer, or False for Boolean.
        """
        raise NotImplementedError("Subclasses must implement")


__all__ = (Encoder.__name__, Decoder.__name__, Coder.__name__)
