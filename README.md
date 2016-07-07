### Coders:
Coders are objects that are capable of encoding / decoding certain values.
Coder is actually an aggregate of both Encoder and Decoder classes.

#### Encoder
The Encoder interface define the following methods:

    def write_to(self, value, stream) -> bytes_written
    def encode(self, value) -> buffer

#### Decoder
The Decoder interface define the following methods:

    def read_from(self, stream) -> value
    def decode(self, buffer) -> value, remainder

### Primitive Types:
Primitive types are classes that **inherits** from Coder.
This means that an **instance** of a primitive type **is a** Coder.
They called Primitive types because they generally deals with built-in types in
python, that have literals in the language. Such types include `int`, `bool`

1. UnsignedInteger
    1. Has a width
    2. Has min and max values
1. Boolean
    1. Is UnsignedInteger.
1. Enum
    1. Is UnsignedInteger.
    2. Values can only be from a pre-defined set.

### Container Types
Container types are classes that **implements** the Coder interface.
This means that the **class itself** is a Coder.
They are used for User-defined Types that contains multiple
primitive / container fields.

1. Record
Defines attributes where each attribute is a Coder, and defines the *order* in
which they should be encoded / decoded.

2. Choice
Has a dictionary of Variants, that maps between a unique value to a Coder.
It also has a Tag field which is a Coder, and it should be able to encode and
decode each of the keys in the Variants dictionary.