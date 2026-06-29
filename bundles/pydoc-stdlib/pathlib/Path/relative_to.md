---
type: reference
title: "pathlib.Path.relative_to"
description: "Return the relative path to another path identified by the passed"
tags: ["pathlib", "stdlib"]
---
# pathlib.Path.relative_to

Return the relative path to another path identified by the passed
arguments.  If the operation is not possible (because this is not
related to the other path), raise ValueError.

The *walk_up* parameter controls whether `..` may be used to resolve
the path.

## Related

- [rename](/pathlib/Path/rename.md)
- [Path](/pathlib/Path.md)
- [absolute](/pathlib/Path/absolute.md)
