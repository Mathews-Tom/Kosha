---
type: reference
title: "pickle.encode_long"
description: "Encode a long to a two's complement little-endian binary string."
tags: ["pickle", "stdlib"]
---
# pickle.encode_long

Encode a long to a two's complement little-endian binary string.
Note that 0 is a special case, returning an empty string, to save a
byte in the LONG1 pickling context.

>>> encode_long(0)
b''
>>> encode_long(255)
b'\xff\x00'
>>> encode_long(32767)
b'\xff\x7f'
>>> encode_long(-256)
b'\x00\xff'
>>> encode_long(-32768)
b'\x00\x80'
>>> encode_long(-128)
b'\x80'
>>> encode_long(127)
b'\x7f'
>>>

## Related

- [islice](/pickle/islice.md)
- [load](/pickle/load.md)
- [loads](/pickle/loads.md)
