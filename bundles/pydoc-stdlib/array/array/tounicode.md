---
type: reference
title: "array.array.tounicode"
description: "Extends this array with data from the unicode string ustr."
tags: ["array", "stdlib"]
---
# array.array.tounicode

Extends this array with data from the unicode string ustr.

Convert the array to a unicode string.  The array must be a unicode type array;
otherwise a ValueError is raised.  Use array.tobytes().decode() to obtain a
unicode string from an array of some other type.

## Related

- [ArrayType](/array/ArrayType.md)
- [buffer_info](/array/ArrayType/buffer_info.md)
- [byteswap](/array/ArrayType/byteswap.md)
