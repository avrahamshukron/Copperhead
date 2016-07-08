class Proxy(object):
    __slots__ = ["_obj", "__weakref__"]

    # A set of attribute names that will not be forwarded to the wrapped
    # object, rather taken from - or set on - the wrapping object itself.
    local_attributes = {"_obj", }

    def __init__(self, obj):
        self._obj = obj

    #
    # Proxying (special cases)
    #
    def __getattribute__(self, name):
        local_attrs = object.__getattribute__(self, "local_attributes")
        if name not in local_attrs:
            return getattr(object.__getattribute__(self, "_obj"), name)
        else:
            return object.__getattribute__(self, name)

    def __delattr__(self, name):
        local_attrs = object.__getattribute__(self, "local_attributes")
        if name not in local_attrs:
            delattr(object.__getattribute__(self, "_obj"), name)
        else:
            object.__delattr__(self, name)

    def __setattr__(self, name, value):
        local_attrs = object.__getattribute__(self, "local_attributes")
        if name not in local_attrs:
            setattr(object.__getattribute__(self, "_obj"), name, value)
        else:
            object.__setattr__(self, name, value)

    def __getitem__(self, index):
        return object.__getattribute__(self, "_obj").__getitem__(index)

    def __nonzero__(self):
        return bool(object.__getattribute__(self, "_obj"))

    def __str__(self):
        return str(object.__getattribute__(self, "_obj"))

    def __repr__(self):
        return repr(object.__getattribute__(self, "_obj"))

    def __len__(self):
        return len(object.__getattribute__(self, "_obj"))

    def __hash__(self):
        return hash(object.__getattribute__(self, "_obj"))

    #
    # Factories
    #
    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__contains__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__eq__', '__float__', '__floordiv__', '__ge__', '__getslice__',
        '__gt__', '__hex__', '__iadd__', '__iand__', '__idiv__', '__idivmod__',
        '__ifloordiv__', '__ilshift__', '__imod__', '__imul__', '__int__',
        '__invert__', '__ior__', '__ipow__', '__irshift__', '__isub__',
        '__iter__', '__itruediv__', '__ixor__', '__le__','__long__',
        '__lshift__', '__lt__', '__mod__', '__mul__', '__ne__', '__neg__',
        '__oct__', '__or__', '__pos__', '__pow__', '__radd__', '__rand__',
        '__rdiv__', '__rdivmod__', '__reduce__', '__reduce_ex__', '__repr__',
        '__reversed__', '__rfloorfiv__', '__rlshift__', '__rmod__', '__rmul__',
        '__ror__', '__rpow__', '__rrshift__', '__rshift__', '__rsub__',
        '__rtruediv__', '__rxor__', '__setitem__', '__setslice__', '__sub__',
        '__truediv__', '__xor__', 'next',
    ]

    @classmethod
    def _create_class_proxy(cls, theclass):
        """creates a proxy for the given class"""

        namespace = cls.create_attrs(theclass)
        proxy_class_name = "%s(%s)" % (cls.__name__, theclass.__name__)
        return type(proxy_class_name, (cls,), namespace)

    @classmethod
    def create_attrs(cls, the_class):
        def make_method(method_name):
            def method(self, *args, **kw):
                func = getattr(self._obj, method_name)
                return func(*args, **kw)

            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(the_class, name):
                namespace[name] = make_method(name)
        return namespace

    def __new__(cls, obj, *args, **kwargs):
        """
        creates an proxy instance referencing `obj`. (obj, *args, **kwargs) are
        passed to this class' __init__, so deriving classes can define an
        __init__ method of their own.
        note: _class_proxy_cache is unique per deriving class (each deriving
        class must hold its own cache)
        """
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}
        try:
            the_class = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = the_class = cls._create_class_proxy(
                obj.__class__)
        ins = object.__new__(the_class)
        the_class.__init__(ins, obj, *args, **kwargs)
        return ins
