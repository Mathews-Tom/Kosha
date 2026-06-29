---
type: reference
title: "array.array.fromunicode"
description: "Extends this array with data from the unicode string ustr."
tags: ["array", "stdlib"]
---
# array.array.fromunicode

Extends this array with data from the unicode string ustr.

The array must be a unicode type array; otherwise a ValueError is raised.
Use array.frombytes(ustr.encode(...)) to append Unicode data to an array of
some other type.

## Related

- [tobytes](/array/array/tobytes.md)
- [tounicode](/array/array/tounicode.md)
- [ArrayType](/array/ArrayType.md)
