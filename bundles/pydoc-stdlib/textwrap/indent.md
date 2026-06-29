---
type: reference
title: "textwrap.indent"
description: "Adds 'prefix' to the beginning of selected lines in 'text'."
tags: ["textwrap", "stdlib"]
---
# textwrap.indent

Adds 'prefix' to the beginning of selected lines in 'text'.

If 'predicate' is provided, 'prefix' will only be added to the lines
where 'predicate(line)' is True. If 'predicate' is not provided,
it will default to adding 'prefix' to all non-empty lines that do not
consist solely of whitespace characters.

## Related

- [shorten](/textwrap/shorten.md)
- [wrap](/textwrap/wrap.md)
- [TextWrapper](/textwrap/TextWrapper.md)
