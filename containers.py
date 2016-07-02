from cStringIO import StringIO
from collections import OrderedDict

from fields import Serializable, Field, EnumField


class RecordBase(type):

    def __new__(mcs, name, bases, attrs):
        order = attrs.get("order")
        if order is None:
            raise ValueError(
                "Subclasses of Record must define an 'order' attribute which "
                "should be a tuple with the names of all the fields in this "
                "class, in the oder they are expected to be encoded/decoded.")

        serializables = {name: field for name, field in attrs.iteritems()
                         if isinstance(field, Field)}
        fields = OrderedDict()
        for field_name in order:
            if field_name not in serializables:
                raise ValueError("%s is not a Serializable field in %s" %
                                 (field_name, name))
            fields[field_name] = serializables[field_name]

        attrs["fields"] = fields
        return super(RecordBase, mcs).__new__(mcs, name, bases, attrs)


class Record(Serializable):

    __metaclass__ = RecordBase

    # This attribute will be overridden by the metaclass, but we declare it here
    # just so that it'll be a known attribute of the class.
    fields = OrderedDict()

    order = ()  # Subclasses must override this field

    def __init__(self, **kwargs):
        # Values of fields which were passed to us.
        values = {name: value for name, value in kwargs.iteritems()
                  if name in self.fields}

        for name, value in values.iteritems():
            setattr(self, name, value)

        # Field names of the fields that
        without_value = set(self._meta.fields.keys()) - set(values.keys())
        for field in without_value:
            setattr(self, field, self._meta.fields[field].get_default())

    def encode(self):
        out = StringIO()
        for name, field in self._meta.fields.iteritems():
            field.encode(getattr(self, name), out)
        return out.getvalue()

    def decode(self, buf):
        pass


def variant(variant_type):
    def creator(cls, *args, **kwargs):
        return cls(variant_type(*args, **kwargs))
    return creator


class ChoiceBase(type):

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
        tag_field = EnumField(values=enum, width=tag_width)
        attrs["tag_field"] = tag_field
        attrs["reverse_variants"] = reverse_variants
        for tag, variant_type in variants.iteritems():
            attrs[variant_type.__name__] = classmethod(
                variant(variant_type=variant_type))

        return super(ChoiceBase, mcs).__new__(mcs, name, bases, attrs)


class Choice(object):
    __metaclass__ = ChoiceBase

    # These attributes will be overridden by the metaclass, but we declare them
    # here just to publicly declare their existence.
    tag_field = None
    variants = {}
    reverse_variants = {}

    def __init__(self, value):
        self.__value = None  # Just to declare the underlying ivar in __init__
        self.value = value

    @property
    def tag(self):
        """
        :return: The tag matching the current value. May be `None` when value
            is `None`
        """
        return self.reverse_variants.get(type(self.value))

    @property
    def value(self):
        # The only reason this method exist, is to create the `value` property,
        # which can then have a setter, which we actually need.
        return self.__value

    @value.setter
    def value(self, value):
        value_type = type(value)
        if value_type not in self.reverse_variants:
            raise ValueError("%s is not one of the variants for this class" %
                             (value_type,))
        self.__value = value

    def encode(self):
        return self.tag_field.encode(self.tag) + self.value.encode()


