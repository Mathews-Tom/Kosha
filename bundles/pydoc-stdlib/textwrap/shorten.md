---
type: reference
title: "textwrap.shorten"
description: "Collapse and truncate the given text to fit in the given width."
tags: ["textwrap", "stdlib"]
---
# textwrap.shorten

Collapse and truncate the given text to fit in the given width.

The text first has its whitespace collapsed.  If it then fits in
the *width*, it is returned as is.  Otherwise, as many words
as possible are joined and then the placeholder is appended::

    >>> textwrap.shorten("Hello  world!", width=12)
    'Hello world!'
    >>> textwrap.shorten("Hello  world!", width=11)
    'Hello [...]'

## Related

- [wrap](/textwrap/wrap.md)
- [TextWrapper](/textwrap/TextWrapper.md)
- [fill](/textwrap/TextWrapper/fill.md)
