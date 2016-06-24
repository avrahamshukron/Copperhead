from unittest import TestCase

from fields import BooleanField


class BooleanFieldTests(TestCase):

    def test_encoding(self):
        f = BooleanField()
        for value, encoded in ((True, "\x01"), (False, "\x00")):
            f.value = value
            self.assertEqual(f.encode(), encoded)

    def test_decoding(self):
        f = BooleanField()
        for value, encoded in ((True, "\x01\xff\xff"), (False, "\x00\xff\xff")):
            rest = f.decode(encoded)
            self.assertEqual(f.value, value)
