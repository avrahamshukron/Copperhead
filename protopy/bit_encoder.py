#! /usr/bin/python

import io


def mask(n):
    return (1 << n) - 1


class BitEncoder:

    def __init__(self):
        self.parts = []

    def push(self, bits, value):
        self.parts.append((bits, value))

    def create(self):
        b = io.BytesIO()
        offset = midvalue = 0
        for bits, value in self.parts:
            toenc = min(8 - offset, bits)
            midvalue <<= toenc
            bits -= toenc
            midvalue |= value >> bits
            value &= mask(bits)
            offset += toenc
            if offset == 8:
                b.write(chr(midvalue).encode())
                offset = midvalue = 0
            while bits >= 8:
                bits -= 8
                b.write(chr(value >> bits).encode())
                value &= mask(bits)
            midvalue <<= bits
            midvalue |= value
            offset += bits
        return b.getvalue()