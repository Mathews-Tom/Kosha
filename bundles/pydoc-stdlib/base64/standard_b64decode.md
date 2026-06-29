---
type: reference
title: "base64.standard_b64decode"
description: "Decode bytes encoded with the standard Base64 alphabet."
tags: ["base64", "stdlib"]
---
# base64.standard_b64decode

Decode bytes encoded with the standard Base64 alphabet.

Argument s is a bytes-like object or ASCII string to decode.  The result
is returned as a bytes object.  A binascii.Error is raised if the input
is incorrectly padded.  Characters that are not in the standard alphabet
are discarded prior to the padding check.

## Related

- [standard_b64encode](/base64/standard_b64encode.md)
- [urlsafe_b64decode](/base64/urlsafe_b64decode.md)
- [urlsafe_b64encode](/base64/urlsafe_b64encode.md)
