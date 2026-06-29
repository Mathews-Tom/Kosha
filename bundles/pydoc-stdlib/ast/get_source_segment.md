---
type: reference
title: "ast.get_source_segment"
description: "Get source code segment of the *source* that generated *node*."
tags: ["ast", "stdlib"]
---
# ast.get_source_segment

Get source code segment of the *source* that generated *node*.

If some location information (`lineno`, `end_lineno`, `col_offset`,
or `end_col_offset`) is missing, return None.

If *padded* is `True`, the first line of a multi-line statement will
be padded with spaces to match its original position.

## Related

- [increment_lineno](/ast/increment_lineno.md)
- [AsyncFor](/ast/AsyncFor.md)
- [AsyncFunctionDef](/ast/AsyncFunctionDef.md)
