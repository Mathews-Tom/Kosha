---
type: reference
title: "urllib.parse.unquote_plus"
description: "Like unquote(), but also replace plus signs by spaces, as required for"
tags: ["urllib.parse", "stdlib"]
---
# urllib.parse.unquote_plus

Like unquote(), but also replace plus signs by spaces, as required for
unquoting HTML form values.

unquote_plus('%7e/abc+def') -> '~/abc def'

## Related

- [unwrap](/urllib/parse/unwrap.md)
- [urldefrag](/urllib/parse/urldefrag.md)
- [DefragResult](/urllib/parse/DefragResult.md)
