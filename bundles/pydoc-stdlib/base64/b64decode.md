---
type: reference
title: "base64.b64decode"
description: "Decode the Base64 encoded bytes-like object or ASCII string s."
tags: ["base64", "stdlib"]
---
# base64.b64decode

Decode the Base64 encoded bytes-like object or ASCII string s.

Optional altchars must be a bytes-like object or ASCII string of length 2
which specifies the alternative alphabet used instead of the '+' and '/'
characters.

The result is returned as a bytes object.  A binascii.Error is raised if
s is incorrectly padded.

If validate is False (the default), characters that are neither in the
normal base-64 alphabet nor the alternative alphabet are discarded prior
to the padding check.  If validate is True, these non-alphabet characters
in the input result in a binascii.Error.
For more information about the strict base64 check, see:

https://docs.python.org/3.11/library/binascii.html#binascii.a2b_base64

## Related

- [b64encode](/base64/b64encode.md)
- [b85decode](/base64/b85decode.md)
- [b85encode](/base64/b85encode.md)
