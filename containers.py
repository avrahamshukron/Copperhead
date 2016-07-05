from cStringIO import StringIO
from collections import OrderedDict

from coders import Coder
from primitives import Enum
from proxy import Proxy


class RecordBase(type, Coder):

    def default_value(self):
        return self()  # Simply return an empty instance

    def __new__(mcs, name, bases, attrs):
        order = attrs.get("order")
        if order is None:
            raise ValueError(
                "Subclasses of Record must define an 'order' attribute which "
                "should be a tuple with the names of all the fields in this "
                "class, in the oder they are expected to be encoded/decoded.")

        serializables = {name: field for name, field in attrs.iteritems()
                         if isinstance(field, Coder)}
        fields = OrderedDict()
        for field_name in order:
            if field_name not in serializables:
                raise ValueError("%s is not a Serializable field in %s" %
                                 (field_name, name))
            fields[field_name] = serializables[field_name]

        attrs["fields"] = fields
        return super(RecordBase, mcs).__new__(mcs, name, bases, attrs)

    def _encode(self, value):
        stream = StringIO()
        self.encode(value, stream)
        return stream.getvalue()

    def encode(self, value, stream):
        for name, coder in self.fields.iteritems():
            coder.encode(getattr(value, name), stream)

    def decode(self, stream):
        # This is valid decoding since self.fields is an *Ordered*Dict, so the
        # decoding is guaranteed to happen in the correct order.
        kwargs = {name: coder.decode_from_stream(stream) for name, coder
                  in self.fields.iteritems()}
        return self(**kwargs)

    def _decode(self, buf):
        stream = StringIO(buf)
        return self.decode_from_stream(stream)


class Record(object):

    __metaclass__ = RecordBase

    # This attribute will be overridden by the metaclass, but we declare it here
    # just so that it'll be a known attribute of the class.
    fields = OrderedDict()

    order = ()  # Subclasses must override this field

    def __init__(self, **kwargs):
        super(Record, self).__init__()
        # Values of fields which were passed to us.
        values = {name: value for name, value in kwargs.iteritems()
                  if name in self.fields}

        for name, value in values.iteritems():
            setattr(self, name, value)

        # Field names of the fields that
        without_value = set(self.fields.keys()) - set(values.keys())
        for field in without_value:
            setattr(self, field, self.fields[field].default_value())


class VariantProxy(Proxy):

    def __init__(self, choice_class, variant_class):
        super(VariantProxy, self).__init__(variant_class)
        object.__setattr__(self, "_choice_class", choice_class)
        # TODO: If variant_class is by itself a Choice, inject each of **its**
        # variants with self as the _choice_class

    @classmethod
    def create_attrs(cls, theclass):
        attrs = super(VariantProxy, cls).create_attrs(theclass)

        def create_choice(self, *args, **kwargs):
            variant_class = object.__getattribute__(self, "_obj")
            variant = variant_class(*args, **kwargs)

            choice_class = object.__getattribute__(self, "_choice_class")
            # TODO: Check here if choice_class has `_choice_class` which will
            # mean that it is a VariantProxy, then recursively call it.
            return choice_class(variant)

        attrs["__call__"] = create_choice
        return attrs


class ChoiceBase(type, Coder):

    def default_value(self):
        return self(tag=self.tag_field.default_value())  # Just an empty Choice

    def __new__(mcs, name, bases, attrs):
        # Get the variants declared for this class.
        variants = attrs.get("variants")
        if variants is None:
            raise ValueError(
                "A Choice subclass must define a variants attribute. "
                "This attribute should be a dictionary mapping between a tag - "
                "which is an integer - to a type")

        reverse_variants = {value: key for key, value in variants.iteritems()}
        if len(reverse_variants) != len(variants):
            raise ValueError(
                "Mapping multiple tags to the same type is not allowed")

        # Get the tag_width.
        tag_width = attrs.get("tag_width")
        if tag_width is None:
            # Defaults to 1 because who will pass 256 variants?!
            tag_width = 1  # Fallback.

        # Just to make sure...
        num_variants = len(variants)
        max_possible = 2 ** (8 * tag_width)
        if num_variants > max_possible:
            raise ValueError(
                "The class declares %s different variants which cannot be "
                "distinguished by tag of %s bytes. You must either lower "
                "the number of variants below %s, or declare a higher "
                "`tag_width`" % (num_variants, tag_width, max_possible))

        enum = {cls.__name__: tag for tag, cls in variants.iteritems()}
        tag_field = Enum(values=enum, width=tag_width)
        attrs["tag_field"] = tag_field
        attrs["reverse_variants"] = reverse_variants
        for variant_type in variants.values():
            attrs[variant_type.__name__] = variant_type
        choice_class = super(ChoiceBase, mcs).__new__(mcs, name, bases, attrs)
        return choice_class

    def _encode(self, value):
        stream = StringIO()
        self.encode(value, stream)
        return stream.getvalue()

    def encode(self, value, stream):
        # Note here that `value` is actually a Choice instance.
        self.tag_field.encode(value.tag, stream)
        variant_cls = self.variants.get(value.tag)
        variant_cls.encode(stream)

    def _decode(self, buf):
        stream = StringIO(buf)
        return self.decode(stream)

    def decode(self, stream):
        tag = self.tag_field.decode(stream)
        variant_cls = self.variants.get(tag)
        return self(tag=tag, value=variant_cls.decode(stream))


class Choice(object):

    __metaclass__ = ChoiceBase

    # These attributes will be overridden by the metaclass, but we declare them
    # here just to publicly declare their existence.
    tag_field = None
    variants = {}
    reverse_variants = {}

    def __init__(self, tag, value=None):
        self.tag = tag
        self.value = value
        if self.value is None:
            variant_coder = self.variants.get(self.tag)
            self.value = variant_coder.default_value()


class Sequence(Coder):

    def __init__(self, element_coder, length_coder=None):
        """
        Initialize new Sequence.
        """
        self.length_coder = length_coder
        self.element_coder = element_coder

    def default_value(self):
        return []

    def _encode(self, value):
        stream = StringIO()
        self.encode(value, stream)
        return stream.getvalue()

    def encode(self, value, stream):
        length = len(value)
        if self.length_coder is not None:
            self.length_coder.encode_into_stream(length, stream)

        for element in value:
            self.element_coder.encode(element, stream)

    def decode(self, stream):
        if self.length_coder is None:
            raise ValueError(
                "Cannot decode a sequence from a stream without a length coder")

        length = self.length_coder.decode(stream)
        return [self.element_coder.decode(stream) for _ in xrange(length)]

    def _decode(self, buf):
        pass


__all__ = (Record.__name__, Choice.__name__, Sequence.__name__)
