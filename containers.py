from cStringIO import StringIO
from collections import OrderedDict

from fields import Serializable, Field


class RecordOptions(object):
    """
    Holds metadata describing a certain Record subclass
    """
    def __init__(self, fields):
        """
        :param fields: OrderedDict of {name: Serializable}
        """
        self.fields = fields


class RecordBase(type):

    def __new__(meta, name, bases, attrs):
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

        _meta = RecordOptions(fields)
        attrs["_meta"] = _meta
        return super(RecordBase, meta).__new__(meta, name, bases, attrs)


class Record(Serializable):

    __metaclass__ = RecordBase

    # This attribute will be overridden by the metaclass, but we declare it here
    # just so that it'll be a known attribute of the class.
    _meta = RecordOptions(None)
    order = ()

    def __init__(self, **kwargs):
        # Values of fields which were passed to us.
        values = {name: value for name, value in kwargs.iteritems()
                  if name in self._meta.fields}

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
