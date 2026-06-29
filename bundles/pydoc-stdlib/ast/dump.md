---
type: reference
title: "ast.dump"
description: "Return a formatted dump of the tree in node. This is mainly useful for"
tags: ["ast", "stdlib"]
---
# ast.dump

Return a formatted dump of the tree in node.  This is mainly useful for
debugging purposes.  If annotate_fields is true (by default),
the returned string will show the names and the values for fields.
If annotate_fields is false, the result string will be more compact by
omitting unambiguous field names.  Attributes such as line
numbers and column offsets are not dumped by default.  If this is wanted,
include_attributes can be set to true.  If indent is a non-negative
integer or string, then the tree will be pretty-printed with that indent
level. None (the default) selects the single line representation.

## Related

- [expr](/ast/expr.md)
- [fix_missing_locations](/ast/fix_missing_locations.md)
- [get_docstring](/ast/get_docstring.md)
