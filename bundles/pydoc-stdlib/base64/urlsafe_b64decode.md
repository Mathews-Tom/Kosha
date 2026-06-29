---
type: reference
title: "base64.urlsafe_b64decode"
description: "Decode bytes using the URL- and filesystem-safe Base64 alphabet."
tags: ["base64", "stdlib"]
---
# base64.urlsafe_b64decode

Decode bytes using the URL- and filesystem-safe Base64 alphabet.

Argument s is a bytes-like object or ASCII string to decode.  The result
is returned as a bytes object.  A binascii.Error is raised if the input
is incorrectly padded.  Characters that are not in the URL-safe base-64
alphabet, and are not a plus '+' or slash '/', are discarded prior to the
padding check.

The alphabet uses '-' instead of '+' and '_' instead of '/'.

## Related

- [urlsafe_b64encode](/base64/urlsafe_b64encode.md)
- [a85decode](/base64/a85decode.md)
- [a85encode](/base64/a85encode.md)
