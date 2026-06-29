---
type: reference
title: "uuid.bytes_.decode"
description: "Decode the bytes using the codec registered for encoding."
tags: ["uuid", "stdlib"]
---
# uuid.bytes_.decode

Decode the bytes using the codec registered for encoding.

encoding
  The encoding with which to decode the bytes.
errors
  The error handling scheme to use for the handling of decoding errors.
  The default is 'strict' meaning that decoding errors raise a
  UnicodeDecodeError. Other possible values are 'ignore' and 'replace'
  as well as any other name registered with codecs.register_error that
  can handle UnicodeDecodeErrors.

## Related

- [endswith](/uuid/bytes_/endswith.md)
- [expandtabs](/uuid/bytes_/expandtabs.md)
- [find](/uuid/bytes_/find.md)
