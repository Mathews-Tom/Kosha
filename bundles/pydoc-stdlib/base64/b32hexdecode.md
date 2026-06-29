---
type: reference
title: "base64.b32hexdecode"
description: "Decode the base32hex encoded bytes-like object or ASCII string s."
tags: ["base64", "stdlib"]
---
# base64.b32hexdecode

Decode the base32hex encoded bytes-like object or ASCII string s.

Optional casefold is a flag specifying whether a lowercase alphabet is
acceptable as input.  For security purposes, the default is False.

The result is returned as a bytes object.  A binascii.Error is raised if
the input is incorrectly padded or if there are non-alphabet
characters present in the input.

## Related

- [b64decode](/base64/b64decode.md)
- [b64encode](/base64/b64encode.md)
- [b85decode](/base64/b85decode.md)
