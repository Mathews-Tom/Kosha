---
type: reference
title: "contextlib.ExitStack"
description: "Context manager for dynamic management of a stack of exit callbacks."
tags: ["contextlib", "stdlib"]
---
# contextlib.ExitStack

Context manager for dynamic management of a stack of exit callbacks.

For example:
    with ExitStack() as stack:
        files = [stack.enter_context(open(fname)) for fname in filenames]
        # All opened files will automatically be closed at the end of
        # the with statement, even if attempts to open files later
        # in the list raise an exception.

## Related

- [enter_context](/contextlib/ExitStack/enter_context.md)
- [push](/contextlib/ExitStack/push.md)
- [GenericAlias](/contextlib/GenericAlias.md)
