from collections import OrderedDict

from coders import Coder
from primitives import Enum


class RecordBase(type, Coder):

    def default_value(self):
        return self()  # Simply return an empty instance

    def __new__(mcs, name, bases, attrs):
        order = attrs.get("order")
        if order is None:
            raise ValueError(
                "Subclasses of Record must define an 'order' attribute which "
                "should be a tuple with the names of all the members in this "
                "class, in the oder they are expected to be encoded/decoded.")

        serializables = {name: field for name, field in attrs.iteritems()
                         if isinstance(field, Coder)}
        members = OrderedDict()
        for field_name in order:
            if field_name not in serializables:
                raise ValueError("%s is not a Serializable field in %s" %
                                 (field_name, name))
            members[field_name] = serializables[field_name]

        attrs["members"] = members
        return super(RecordBase, mcs).__new__(mcs, name, bases, attrs)

    def write_to(self, value, stream):
        written = 0
        for name, coder in self.members.iteritems():
            written += coder.write_to(getattr(value, name), stream)
        return written

    def read_from(self, stream):
        # This is valid decoding since self.fields is an *Ordered*Dict, so the
        # decoding is guaranteed to happen in the correct order.
        kwargs = {name: coder.read_from(stream) for name, coder
                  in self.members.iteritems()}
        return self(**kwargs)


class Record(object):

    __metaclass__ = RecordBase

    # This attribute will be overridden by the metaclass, but we declare it here
    # just so that it'll be a known attribute of the class.
    members = OrderedDict()

    order = ()  # Subclasses must override this field

    def __init__(self, **kwargs):
        super(Record, self).__init__()
        # Values of fields which were passed to us.
        values = {name: value for name, value in kwargs.iteritems()
                  if name in self.members}

        for name, value in values.iteritems():
            setattr(self, name, value)

        # Field names of the fields that
        without_value = set(self.members.keys()) - set(values.keys())
        for field in without_value:
            setattr(self, field, self.members[field].default_value())


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
        tag_field = Enum(members=enum, width=tag_width)
        attrs["tag_field"] = tag_field
        attrs["reverse_variants"] = reverse_variants
        for variant_type in variants.values():
            attrs[variant_type.__name__] = variant_type
        choice_class = super(ChoiceBase, mcs).__new__(mcs, name, bases, attrs)
        return choice_class

    def write_to(self, value, stream):
        # Note here that `value` is actually a Choice instance.
        written = self.tag_field.write_to(value.tag, stream)
        variant_cls = self.variants.get(value.tag)
        written += variant_cls.write_to(stream)
        return written

    def read_from(self, stream):
        tag = self.tag_field.read_from(stream)
        variant_cls = self.variants.get(tag)
        return self(tag=tag, value=variant_cls.read_from(stream))


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


__all__ = (Record.__name__, Choice.__name__)
