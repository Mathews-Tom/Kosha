---
type: reference
title: "struct.pack_into"
description: "pack_into(format, buffer, offset, v1, v2, ...)"
tags: ["struct", "stdlib"]
---
# struct.pack_into

pack_into(format, buffer, offset, v1, v2, ...)

Pack the values v1, v2, ... according to the format string and write
the packed bytes into the writable buffer buf starting at offset.  Note
that the offset is a required argument.  See help(struct) for more
on format strings.

## Related

- [unpack](/struct/unpack.md)
- [unpack_from](/struct/unpack_from.md)
- [iter_unpack](/struct/iter_unpack.md)
