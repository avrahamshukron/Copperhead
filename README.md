# ProtoPy
**ProtoPy** is a Python framework designed to provide an easy API for
serializing structured data.

The main design goals of this framework are:
1. Simplify the API and hide all the complexity in the framework.
2. Provide total control over the _wire format_.

>> _Wire Format_ refers to the actual binary layout of data when it is being
passed "On the wire" - that is - sent over the network, saved to disk etc.

## Core Concepts

### Coders:

The most basic entities in the framework are **coders**.

Coders are objects that are capable of serializing a certain type of values.
The `Coder` class defines the coder interface, and is actually an aggregate of
both `Encoder` and `Decoder` classes.

#### Encoder

The Encoder interface define the following methods:

    def write_to(self, value, stream) -> bytes_written

The `write_to` method serializes a value and writes it into a stream.
It returns the number of bytes written.

    def encode(self, value) -> buffer

The `encode` method serializes a value and returns the result as a string.

#### Decoder

The Decoder interface define the following methods:

    def read_from(self, stream) -> value

The `read_from` method read and decodes a value from a stream, and returns the
decoded value.

    def decode(self, buffer) -> value, remainder

The `decode` method decodes a value from a buffer, and returns the
decoded value and the remaining buffer.

---
### Primitives
Primitive types are classes that **inherits** from Coder.
This means that an **instance** of a primitive type **is a** Coder.
They called Primitive types because they generally deals with built-in types in
python, that have literals in the language. Such types include `int`, `bool`

---
### Containers
Container types are classes that **implements** the Coder interface.
This means that the **class itself** is a Coder.
They are used for User-defined Types that contains multiple
primitive / container fields.

#### Record
Defines attributes where each attribute is a Coder, and defines the *order* in
which they should be encoded / decoded.

#### Choice
Has a dictionary of Variants, that maps between a unique value to a Coder.
It also has a Tag field which is a Coder, and it should be able to encode and
decode each of the keys in the Variants dictionary.