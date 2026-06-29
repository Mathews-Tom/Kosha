---
type: reference
title: "urllib.parse.quote_from_bytes"
description: "Like quote(), but accepts a bytes object rather than a str, and does"
tags: ["urllib.parse", "stdlib"]
---
# urllib.parse.quote_from_bytes

Like quote(), but accepts a bytes object rather than a str, and does
not perform string-to-bytes encoding.  It always returns an ASCII string.
quote_from_bytes(b'abc def?') -> 'abc%20def%3f'

## Related

- [quote_plus](/urllib/parse/quote_plus.md)
- [unquote](/urllib/parse/unquote.md)
- [unquote_plus](/urllib/parse/unquote_plus.md)
