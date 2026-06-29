---
type: reference
title: "http.HTTPMethod.encode"
description: "Encode the string using the codec registered for encoding."
tags: ["http", "stdlib"]
---
# http.HTTPMethod.encode

Encode the string using the codec registered for encoding.

encoding
  The encoding in which to encode the string.
errors
  The error handling scheme to use for encoding errors.
  The default is 'strict' meaning that encoding errors raise a
  UnicodeEncodeError.  Other possible values are 'ignore', 'replace' and
  'xmlcharrefreplace' as well as any other name registered with
  codecs.register_error that can handle UnicodeEncodeErrors.

## Related

- [endswith](/http/HTTPMethod/endswith.md)
- [expandtabs](/http/HTTPMethod/expandtabs.md)
- [find](/http/HTTPMethod/find.md)
