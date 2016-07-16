from collections import OrderedDict

import sys
from functools import total_ordering

import operator

from coders import Coder, SelfEncodable
from primitives import Enum, UnsignedInteger
from proxy import Proxy


class RecordBase(type, Coder):
    """
    Metaclass for Record
    """

    def default_value(self):
        return self()  # Simply return an empty instance

    def __new__(mcs, name, bases, attrs):
        """
        Create a new Record (sub)class
        """
        # Extract all the attributes of type Member.
        coders = {name: field for name, field in attrs.iteritems()
                  if isinstance(field, Member)}
        for member_name, member in coders.iteritems():
            if not isinstance(member.coder, Coder):
                raise ValueError(
                    "%s.%s: Member does not contain a Coder subclass" %
                    (name, member_name))

        # Sort all the members.
        coder_items = coders.items()
        coder_items.sort(key=operator.itemgetter(1))

        # Extract the actual coders, and throw away the Member wrapper.
        members = OrderedDict()
        for member_name, member in coder_items:
            members[member_name] = member.coder
        attrs.update(members)

        # Add `members` to the class
        attrs["members"] = members
        # Create and return the class
        return super(RecordBase, mcs).__new__(mcs, name, bases, attrs)

    def write_to(self, value, stream):
        # Note that `value` is actually a Record **instance**
        return value.write_to(stream)

    def read_from(self, stream):
        # This is valid decoding since self.fields is an *Ordered*Dict, so the
        # decoding is guaranteed to happen in the correct order.
        kwargs = {name: coder.read_from(stream) for name, coder
                  in self.members.iteritems()}
        return self(**kwargs)


@total_ordering
class Member(object):
    """
    Represents a member of a record.
    """
    creation_counter = 0

    def __init__(self, coder, order=None):
        """
        Initialize a new Member.

        :param coder: A Coder object
        :param order: Optional. User-defined order to override the default
            order, which is the order of declaration.
        """
        self.creation_counter = Member.creation_counter
        Member.creation_counter += 1
        self.coder = coder
        self.order = order if order is not None else sys.maxint

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self.coder == other.coder and self.order == other.order

    def __lt__(self, other):
        if self.order < other.order:
            return True
        return self.creation_counter < other.creation_counter


class Record(SelfEncodable):
    """
    An object that holds multiple "Member", which are attributes that will be
    encoded / decoded by a certain order.
    """
    __metaclass__ = RecordBase

    # This attribute will be overridden by the metaclass, but we declare it here
    # just so that it'll be a known attribute of the class.
    members = OrderedDict()

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

    def write_to(self, stream):
        written = 0
        for name, coder in self.members.iteritems():
            written += coder.write_to(getattr(self, name), stream)
        return written

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        for member in self.members.keys():
            if getattr(self, member) != getattr(other, member):
                return False
        return True


class ChoiceBase(type, Coder):
    """
    Metaclass for Choice
    """

    def default_value(self):
        return self(tag=self.tag_field.default_value())  # Just an empty Choice

    def __new__(mcs, name, bases, attrs):
        """
        Create a new Choice (sub)class.
        """
        # Get the variants declared for this class.
        variants = attrs.pop("variants", None)
        if variants is None:
            raise ValueError(
                "A Choice subclass must define a variants attribute. "
                "This attribute should be a dictionary mapping between a tag - "
                "which is an integer - to a type")

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

        # Create the `tag_field` enum field for this class.
        enum = {cls.__name__: tag for tag, cls in variants.iteritems()}
        tag_field = Enum(members=enum, width=tag_width)
        attrs["tag_field"] = tag_field

        # Create the class here, because we need it for the next steps
        choice_class = super(ChoiceBase, mcs).__new__(mcs, name, bases, attrs)

        # Replace the actual variants with a Variant Proxy object.
        variants = {tag: Variant(choice_class, tag, variant_type)
                    for tag, variant_type in variants.iteritems()}
        # Add variants and its reverse version as an attributes
        choice_class.variants = variants
        choice_class.reverse_variants = {
            value: key for key, value in variants.iteritems()
        }

        # Add each variant as an attribute to the Choice class
        for tag, variant in variants.iteritems():
            setattr(choice_class, variant.__name__, variant)

        return choice_class

    def write_to(self, value, stream):
        # Note here that `value` is actually a Choice instance.
        return value.write_to(stream)

    def read_from(self, stream):
        tag = self.tag_field.read_from(stream)
        variant_cls = self.variants.get(tag)
        return self(tag=tag, value=variant_cls.read_from(stream))


class Choice(SelfEncodable):
    """
    Represents an object that can be interpreted in multiple ways, each
    distinguished by a special identifier called "tag".
    """
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

    def write_to(self, stream):
        written = self.tag_field.write_to(self.tag, stream)
        variant_cls = self.variants.get(self.tag)
        written += variant_cls.write_to(self.value, stream)
        return written

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        if self.tag != other.tag:
            return False
        return self.value == other.value


class Variant(Proxy):
    """
    A special object that wraps a Coder specified for a Choice.

    Why do we need a Variant?
    Say we have a Choice subclass named Command, with a variant named Upgrade.
    The desired API of creating and Upgrade Command is Command.Upgrade().
    For this to work we need a special object that looks like the variant's
    class, but when __call__ed, actually creates an instance of the variant,
    wrapped in an instance of the containing Choice.
    This is the purpose of this class.
    """

    __slots__ = ("_tag", "_parent_choice")

    local_attributes = Proxy.local_attributes.union(
        set(__slots__)
    )

    def __init__(self, choice_class, tag, variant_class):
        super(Variant, self).__init__(variant_class)
        self._parent_choice = choice_class
        self._tag = tag
        # This is where we create the complete chain of Choices and their
        # VariantProxy objects.
        # If variant_class is by itself a Choice, inject each of **its**
        # variants with self as the _choice_class
        if issubclass(self._obj, Choice):
            for _, variant in self._obj.variants.iteritems():
                variant._parent_choice = self

    def create_choice(self, *args, **kwargs):
        variant = self._obj(*args, **kwargs)
        # Now this is where the magic happens:
        # If parent_choice is by itself a variant of another Choice, then it is
        # actually a VariantProxy, which means its __call__ method is overridden
        # with **this** function, thus resulting in a recursive call that will
        # create the out-most Choice all the way up using the variants created
        # along the way as the values.
        return self._parent_choice(self._tag, variant)

    @classmethod
    def create_attrs(cls, the_class):
        attrs = super(Variant, cls).create_attrs(the_class)
        attrs["__call__"] = cls.create_choice
        return attrs


# noinspection PyProtectedMember
class BitMask(object):
    """
    Simple descriptor class for bit-mask fields.
    """
    __slots__ = ("mask", "shift")

    def __init__(self, mask):
        """
        Initialize new BitMask field.

        :param mask: int: the bit-mask for this field.
        """
        self.mask = mask
        # Find the index of the first "1" bit from the right. This index will
        # be used to extract the value of this specific field from the
        # containing integer.
        binary = bin(mask)[2:]  # Removes the "0b" prefix
        self.shift = len(binary)
        for index, bit in enumerate(reversed(binary)):
            if bit == "1":
                self.shift = index
                break

    def __get__(self, instance, owner):
        return (instance._value & self.mask) >> self.shift

    def __set__(self, instance, value):
        instance._value |= (self.mask & (value << self.shift))


class BitMaskedIntegerMeta(type, Coder):
    """
    Meta class for creating bitmasked integer classes.
    """

    def __new__(mcs, name, bases, attrs):
        if "width" not in attrs:
            raise ValueError("BitMask field must define the width attribute")

        width = attrs.get("width")
        coder = UnsignedInteger(width=width)
        attrs["_coder"] = coder

        masks = {name: value for name, value in attrs.iteritems()
                 if isinstance(value, BitMask)}
        attrs["masks"] = masks
        return super(BitMaskedIntegerMeta, mcs).__new__(mcs, name, bases, attrs)

    def write_to(self, value, stream):
        # value is an instance of BitFields
        return value.write_to(stream)

    def read_from(self, stream):
        value = self._coder.read_from(stream)
        return self.from_int(value)

    def default_value(self):
        return self()


class BitMaskedInteger(SelfEncodable):
    __metaclass__ = BitMaskedIntegerMeta
    width = 1  # Subclasses must override
    _coder = None  # Will be set by the metaclass
    masks = {}  # Will be set by the metaclass

    @classmethod
    def from_int(cls, value):
        v = cls()
        v._value = value
        return v

    def __init__(self, **kwargs):
        self._value = 0  # start zeroed.
        mine = {name: value for name, value in kwargs.iteritems()
                if name in self.masks}
        for name, value in mine.iteritems():
            setattr(self, name, value)

    def write_to(self, stream):
        return self._coder.write_to(self._value, stream)

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False
        return self._value == other._value

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return "{name}: {masks}".format(
            name=self.__class__.__name__,
            masks={name: getattr(self, name) for name in self.masks.iterkeys()}
        )


__all__ = (Record.__name__, Choice.__name__)
