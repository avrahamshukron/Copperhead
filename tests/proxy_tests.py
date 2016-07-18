from unittest import TestCase

from protopy.proxy import Proxy


class Foo(object):

    def __init__(self):
        self.foo = "hello"
        self.bar = "world"

    def __int__(self):
        return 1


class FooProxy(Proxy):
    __slots__ = ("baz", "bak")
    local_attributes = Proxy.local_attributes.union(set(__slots__))

    def __init__(self, obj, **kwargs):
        super(FooProxy, self).__init__(obj)
        self.baz = 1
        self.bak = 1


class ProxyTest(TestCase):

    def test_attribute_proxying(self):
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
        p = Proxy(v)
        self.assertEqual(str(v), str(p))
        self.assertEqual(repr(v), repr(p))

        v = Foo()
        p = FooProxy(v)
        self.assertEqual(int(v), int(p))

        l = [1, ]
        p = Proxy(l)
        self.assertEqual(bool(p), bool(l))
        self.assertEqual(len(p), len(l))
        self.assertEqual(p[0], l[0])


