---
type: reference
title: "textwrap.TextWrapper.wrap"
description: "wrap(text : string) -> [string]"
tags: ["textwrap", "stdlib"]
---
# textwrap.TextWrapper.wrap

wrap(text : string) -> [string]

Reformat the single paragraph in 'text' so it fits in lines of
no more than 'self.width' columns, and return a list of wrapped
lines.  Tabs in 'text' are expanded with string.expandtabs(),
and all other whitespace characters (including newline) are
converted to space.

## Related

- [dedent](/textwrap/dedent.md)
- [fill](/textwrap/fill.md)
- [indent](/textwrap/indent.md)
