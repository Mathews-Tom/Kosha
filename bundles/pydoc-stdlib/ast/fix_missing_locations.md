---
type: reference
title: "ast.fix_missing_locations"
description: "When you compile a node tree with compile(), the compiler expects lineno and"
tags: ["ast", "stdlib"]
---
# ast.fix_missing_locations

When you compile a node tree with compile(), the compiler expects lineno and
col_offset attributes for every node that supports them.  This is rather
tedious to fill in for generated nodes, so this helper adds these attributes
recursively where not already set, by setting them to the values of the
parent node.  It works recursively starting at *node*.

## Related

- [get_docstring](/ast/get_docstring.md)
- [get_source_segment](/ast/get_source_segment.md)
- [increment_lineno](/ast/increment_lineno.md)
