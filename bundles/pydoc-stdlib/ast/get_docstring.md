---
type: reference
title: "ast.get_docstring"
description: "Return the docstring for the given node or None if no docstring can"
tags: ["ast", "stdlib"]
---
# ast.get_docstring

Return the docstring for the given node or None if no docstring can
be found.  If the node provided does not have docstrings a TypeError
will be raised.

If *clean* is `True`, all tabs are expanded to spaces and any whitespace
that can be uniformly removed from the second line onwards is removed.

## Related

- [get_source_segment](/ast/get_source_segment.md)
- [increment_lineno](/ast/increment_lineno.md)
- [AsyncFor](/ast/AsyncFor.md)
