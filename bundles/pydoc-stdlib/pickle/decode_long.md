---
type: reference
title: "pickle.decode_long"
description: "Decode a long from a two's complement little-endian binary string."
tags: ["pickle", "stdlib"]
---
# pickle.decode_long

Decode a long from a two's complement little-endian binary string.

>>> decode_long(b'')
0
>>> decode_long(b"\xff\x00")
255
>>> decode_long(b"\xff\x7f")
32767
>>> decode_long(b"\x00\xff")
-256
>>> decode_long(b"\x00\x80")
-32768
>>> decode_long(b"\x80")
-128
>>> decode_long(b"\x7f")
127

## Related

- [dump](/pickle/dump.md)
- [dumps](/pickle/dumps.md)
- [encode_long](/pickle/encode_long.md)
