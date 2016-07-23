import operator
import sys
from collections import OrderedDict
from functools import total_ordering

from coders import Coder, SelfEncodable
from primitives import UnsignedInteger, ByteOrder
import enum34
from proxy import Proxy


class EnumerationMeta(enum34.EnumMeta, Coder):
    """
    Metaclass for Coder-compliant Enums
    """

    DEFAULT_WIDTH = 1
    DEFAULT_BYTE_ORDER = ByteOrder.MSB_FIRST

    def __new__(mcs, name, bases, classdict):
        width = classdict.pop("__width__", mcs.DEFAULT_WIDTH)
        byte_oder = classdict.pop("__byte_order__", mcs.DEFAULT_BYTE_ORDER)
        coder = UnsignedInteger(width=width, byte_order=byte_oder)
        classdict["__coder__"] = coder
        return super(EnumerationMeta, mcs).__new__(mcs, name, bases, classdict)

    def default_value(self):
        """
        :return: The first ordinal member in the enum.
        """
        if len(self.__members__) == 0:
            raise ValueError("%s class does not have any members" %
                             (self.__name__,))

        _, value = self.__members__.items()[0]
        return value

    def write_to(self, value, stream):
        self.__coder__.write_to(self(value), stream)

    def read_from(self, stream):
        value = self.__coder__.read_from(stream)
        return self(value)


class Enumeration(int, SelfEncodable, enum34.Enum):
    """
    Superclass for enumeration types.
    Based on the Enum class from the enum34 package, back-porting Enum from
    Python 3.4
    """
    __metaclass__ = EnumerationMeta
    __coder__ = None  # Set by the metaclass

    def write_to(self, stream):
        return self.__coder__.write_to(self, stream)


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

    Member objects define the order in which each record field will be
    encoded / decoded.
    """

    # Used to obtain the order of members declared in a Record subclass.
    creation_counter = 0

    def __init__(self, coder, order=None):
        """
        Initialize a new Member.

        By default, members are ordered of their declaration.
        The user can override this behavior by passing the `order` parameter for
        some or all of the members.
        If an order value is specified for a member, it'll always come before
        any field that doesn't have an order defined for it. If two members have
        order defined, they will be ordered by it.

        :param coder: A Coder object
        :param order: Optional. User-defined order to override the default
            order, which is the order of declaration.
        """
        self.creation_counter = Member.creation_counter
        Member.creation_counter += 1
        self.coder = coder
        self._user_defined_order = order is not None
        self.order = order if order is not None else sys.maxint

    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return False

        if self.coder != other.coder:
            return False

        if self._user_defined_order != other._user_defined_order:
            return False

        if self._user_defined_order and other._user_defined_order:
            return self.order == other.order

        return self.creation_counter == other.creation_counter

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if not isinstance(other, type(self)):
            raise ValueError(
                "Cannot compare %s with %s" %
                (self.__class__.__name__,
                 other.__class__.__name__))

        # I have user-define order.
        if self._user_defined_order:
            return self.order < other.order

        if other._user_defined_order:
            # I don't have user-defined order, but `other` has.
            return False

        # Default. Decide by creation order.
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

    def __ne__(self, other):
        return not self.__eq__(other)


class ChoiceBase(type, Coder):
    """
    Metaclass for Choice
    """

    def default_value(self):
        return self(tag=self.tag_enum.default_value())  # Just an empty Choice

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

        # Create the tags enum for this class.
        values = {cls.__name__: tag for tag, cls in variants.iteritems()}
        variants_enum = EnumerationMeta(
            "%sTag" % (name,), (Enumeration,), values)
        attrs["tag_enum"] = variants_enum

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
        tag = self.tag_enum.read_from(stream)
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
    tag_enum = None
    variants = {}
    reverse_variants = {}

    def __init__(self, tag, value=None):
        """
        Initialize a new Choice instance.

        :param tag: The id of this instance. An instance of Class.tag_enum
        :param value: Optional. A value corresponding to `tag`.
        """
        self.tag = self.tag_enum(tag)
        self.value = value
        if self.value is None:
            variant_coder = self.variants.get(self.tag)
            self.value = variant_coder.default_value()

    def write_to(self, stream):
        written = self.tag_enum.write_to(self.tag_enum(self.tag), stream)
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

    # Attributes which are not proxied
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
        # Make this proxy callable, ultimately resulting in it being a `type`,
        # since it is now capable of creating instances.
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
        # Find the index of the first "1" bit from the right. This index will be
        # used to extract the value of this specific field from the containing
        # integer. If no 1 is found, the mask is 0 which is meaningless. In that
        # case, shift will be also 0.
        binary = bin(mask)[2:][::-1]  # Remove the '0b' and reverse.
        self.shift = max(binary.find("1"), 0)

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

__all__ = (Record.__name__, Choice.__name__, Enumeration.__name__)
