---
type: reference
title: "base64.b16decode"
description: "Decode the Base16 encoded bytes-like object or ASCII string s."
tags: ["base64", "stdlib"]
---
# base64.b16decode

Decode the Base16 encoded bytes-like object or ASCII string s.

Optional casefold is a flag specifying whether a lowercase alphabet is
acceptable as input.  For security purposes, the default is False.

The result is returned as a bytes object.  A binascii.Error is raised if
s is incorrectly padded or if there are non-alphabet characters present
in the input.

## Related

- [b32decode](/base64/b32decode.md)
- [b32hexdecode](/base64/b32hexdecode.md)
- [b64decode](/base64/b64decode.md)
