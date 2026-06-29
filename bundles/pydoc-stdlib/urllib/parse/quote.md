---
type: reference
title: "urllib.parse.quote"
description: "quote('abc def') -> 'abc%20def'"
tags: ["urllib.parse", "stdlib"]
---
# urllib.parse.quote

quote('abc def') -> 'abc%20def'

Each part of a URL, e.g. the path info, the query, etc., has a
different set of reserved characters that must be quoted. The
quote function offers a cautious (not minimal) way to quote a
string for most of these parts.

RFC 3986 Uniform Resource Identifier (URI): Generic Syntax lists
the following (un)reserved characters.

unreserved    = ALPHA / DIGIT / "-" / "." / "_" / "~"
reserved      = gen-delims / sub-delims
gen-delims    = ":" / "/" / "?" / "#" / "[" / "]" / "@"
sub-delims    = "!" / "$" / "&" / "'" / "(" / ")"
              / "*" / "+" / "," / ";" / "="

Each of the reserved characters is reserved in some component of a URL,
but not necessarily in all of them.

The quote function %-escapes all characters that are neither in the
unreserved chars ("always safe") nor the additional chars set via the
safe arg.

The default for the safe arg is '/'. The character is reserved, but in
typical usage the quote function is being called on a path where the
existing slash characters are to be preserved.

Python 3.7 updates from using RFC 2396 to RFC 3986 to quote URL strings.
Now, "~" is included in the set of unreserved characters.

string and safe may be either str or bytes objects. encoding and errors
must not be specified if string is a bytes object.

The optional encoding and errors parameters specify how to deal with
non-ASCII characters, as accepted by the str.encode method.
By default, encoding='utf-8' (characters are encoded with UTF-8), and
errors='strict' (unsupported characters raise a UnicodeEncodeError).

## Related

- [quote_from_bytes](/urllib/parse/quote_from_bytes.md)
- [quote_plus](/urllib/parse/quote_plus.md)
- [unquote](/urllib/parse/unquote.md)
