---
type: reference
title: "urllib.parse.unquote"
description: "Replace %xx escapes by their single-character equivalent. The optional"
tags: ["urllib.parse", "stdlib"]
---
# urllib.parse.unquote

Replace %xx escapes by their single-character equivalent. The optional
encoding and errors parameters specify how to decode percent-encoded
sequences into Unicode characters, as accepted by the bytes.decode()
method.
By default, percent-encoded sequences are decoded with UTF-8, and invalid
sequences are replaced by a placeholder character.

unquote('abc%20def') -> 'abc def'.

## Related

- [unquote_plus](/urllib/parse/unquote_plus.md)
- [unwrap](/urllib/parse/unwrap.md)
- [urldefrag](/urllib/parse/urldefrag.md)
