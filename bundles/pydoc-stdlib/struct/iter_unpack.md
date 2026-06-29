---
type: reference
title: "struct.iter_unpack"
description: "Return an iterator yielding tuples unpacked from the given bytes."
tags: ["struct", "stdlib"]
---
# struct.iter_unpack

Return an iterator yielding tuples unpacked from the given bytes.

The bytes are unpacked according to the format string, like
a repeated invocation of unpack_from().

Requires that the bytes length be a multiple of the format struct size.

## Related

- [pack](/struct/pack.md)
- [pack_into](/struct/pack_into.md)
- [unpack](/struct/unpack.md)
