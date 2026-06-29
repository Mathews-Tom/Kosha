---
type: reference
title: "base64.b64encode"
description: "Encode the bytes-like object s using Base64 and return a bytes object."
tags: ["base64", "stdlib"]
---
# base64.b64encode

Encode the bytes-like object s using Base64 and return a bytes object.

Optional altchars should be a byte string of length 2 which specifies an
alternative alphabet for the '+' and '/' characters.  This allows an
application to e.g. generate url or filesystem safe Base64 strings.

## Related

- [b85decode](/base64/b85decode.md)
- [b85encode](/base64/b85encode.md)
- [encodebytes](/base64/encodebytes.md)
