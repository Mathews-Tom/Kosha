---
type: reference
title: "re.error"
description: "Exception raised for invalid regular expressions."
tags: ["re", "stdlib"]
---
# re.error

Exception raised for invalid regular expressions.

Attributes:

    msg: The unformatted error message
    pattern: The regular expression pattern
    pos: The index in the pattern where compilation failed (may be None)
    lineno: The line corresponding to pos (may be None)
    colno: The column corresponding to pos (may be None)

## Related

- [findall](/re/findall.md)
- [finditer](/re/finditer.md)
- [fullmatch](/re/fullmatch.md)
