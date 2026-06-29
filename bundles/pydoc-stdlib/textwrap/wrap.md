---
type: reference
title: "textwrap.wrap"
description: "Wrap a single paragraph of text, returning a list of wrapped lines."
tags: ["textwrap", "stdlib"]
---
# textwrap.wrap

Wrap a single paragraph of text, returning a list of wrapped lines.

Reformat the single paragraph in 'text' so it fits in lines of no
more than 'width' columns, and return a list of wrapped lines.  By
default, tabs in 'text' are expanded with string.expandtabs(), and
all other whitespace characters (including newline) are converted to
space.  See TextWrapper class for available keyword args to customize
wrapping behaviour.

## Related

- [TextWrapper](/textwrap/TextWrapper.md)
- [fill](/textwrap/TextWrapper/fill.md)
- [wrap](/textwrap/TextWrapper/wrap.md)
