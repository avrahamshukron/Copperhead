from unittest import TestCase

from protopy.proxy import Proxy


class Foo(object):

    def __init__(self):
        self.foo = "hello"
        self.bar = "world"

    def __str__(self):
        return "str"

    def __repr__(self):
        return "repr"


class FooProxy(Proxy):
    __slots__ = ("baz", "bak")
    local_attributes = Proxy.local_attributes.union(set(__slots__))

    def __init__(self, obj, **kwargs):
        super(FooProxy, self).__init__(obj)
        self.baz = 1
        self.bak = 1


class ProxyTest(TestCase):

    def test_attributes(self):
        f = Foo()
        p = FooProxy(f)

        # __getattribute__
        self.assertIs(p.foo, f.foo)
        self.assertIs(p.bar, f.bar)

        # __setattr__
        p.foo = "what?"
        self.assertIs(p.foo, f.foo)

        # __delattr__
        delattr(p, "bar")
        self.assertFalse(hasattr(f, "bar"))

        self.assertTrue(hasattr(p, "baz"))
        delattr(p, "baz")
        self.assertFalse(hasattr(p, "baz"))

    def test_special_funcs(self):
        v = 6
        p = FooProxy(v)
        self.assertEqual(str(v), str(p))
        self.assertEqual(repr(v), repr(p))
