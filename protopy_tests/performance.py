from time import time


s = time()
from dummy import Command
e = time()

print "Import took ", e - s

s = time()
b = Command.Dummy(counter_size=10).encode()
e = time()

print "Encoding took ", e - s
print "Encoded buffer: ", b

s = time()
d = Command.decode(b)
e = time()

print "Decoding took ", e - s
