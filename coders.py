from abc import ABCMeta, abstractmethod


class Encoder(object):
    __metaclass__ = ABCMeta

    def encode(self, value, stream):
        """
        Encode a value into a stream.

        :param value: The value to encode.
        :param stream: A writeable file-like object.
        :raise ValueError: If `value` could not be encoded.
        """
        # Naive implementation. Subclasses are encourage to override if it
        # makes more sense.
        stream.write(self._encode(value))

    @abstractmethod
    def _encode(self, value):
        """
        Encode the given value as a sequence of bytes.

        :param value: The value to encode.
        :return: A sequence of bytes representing `value`
        :raise ValueError: If `value` could not be encoded.
        """
        pass


class Decoder(object):
    __metaclass__ = ABCMeta

    @abstractmethod
    def decode(self, stream):
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
        pass

    @abstractmethod
    def _decode(self, buf):
        """
        Decode a value from a buffer.

        :param buf: A sequence of bytes.
        :return: (value, remainder) A tuple of the value decoded and the
            remainder of the buffer.
        :raise ValueError: If the buffer cannot be decoded.
        """
        pass


class Coder(Encoder, Decoder):
    """
    Aggregates both Encoder and Decoder interfaces.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def default_value(self):
        """
        Return the value that is considered "default" or "empty" for this type.
         For example, this might be 0 for Integer, or False for Boolean.
        """
        pass
