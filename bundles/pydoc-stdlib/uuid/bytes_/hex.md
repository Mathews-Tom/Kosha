---
type: reference
title: "uuid.bytes_.hex"
description: "Create a string of hexadecimal numbers from a bytes object."
tags: ["uuid", "stdlib"]
---
# uuid.bytes_.hex

Create a string of hexadecimal numbers from a bytes object.

  sep
    An optional single character or byte to separate hex bytes.
  bytes_per_sep
    How many bytes between separators.  Positive values count from the
    right, negative values count from the left.

Example:
>>> value = b'\xb9\x01\xef'
>>> value.hex()
'b901ef'
>>> value.hex(':')
'b9:01:ef'
>>> value.hex(':', 2)
'b9:01ef'
>>> value.hex(':', -2)
'b901:ef'

## Related

- [isalnum](/uuid/bytes_/isalnum.md)
- [isalpha](/uuid/bytes_/isalpha.md)
- [isascii](/uuid/bytes_/isascii.md)
