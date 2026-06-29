---
type: reference
title: "base64.b32decode"
description: "Decode the base32 encoded bytes-like object or ASCII string s."
tags: ["base64", "stdlib"]
---
# base64.b32decode

Decode the base32 encoded bytes-like object or ASCII string s.

Optional casefold is a flag specifying whether a lowercase alphabet is
acceptable as input.  For security purposes, the default is False.

RFC 3548 allows for optional mapping of the digit 0 (zero) to the
letter O (oh), and for optional mapping of the digit 1 (one) to
either the letter I (eye) or letter L (el).  The optional argument
map01 when not None, specifies which letter the digit 1 should be
mapped to (when map01 is not None, the digit 0 is always mapped to
the letter O).  For security purposes the default is None, so that
0 and 1 are not allowed in the input.

The result is returned as a bytes object.  A binascii.Error is raised if
the input is incorrectly padded or if there are non-alphabet
characters present in the input.

## Related

- [b32hexdecode](/base64/b32hexdecode.md)
- [b64decode](/base64/b64decode.md)
- [b64encode](/base64/b64encode.md)
