---
type: reference
title: "contextlib.AsyncExitStack"
description: "Async context manager for dynamic management of a stack of exit"
tags: ["contextlib", "stdlib"]
---
# contextlib.AsyncExitStack

Async context manager for dynamic management of a stack of exit
callbacks.

For example:
    async with AsyncExitStack() as stack:
        connections = [await stack.enter_async_context(get_connection())
            for i in range(5)]
        # All opened connections will automatically be released at the
        # end of the async with statement, even if attempts to open a
        # connection later in the list raise an exception.

## Related

- [enter_async_context](/contextlib/AsyncExitStack/enter_async_context.md)
- [enter_context](/contextlib/AsyncExitStack/enter_context.md)
- [push](/contextlib/AsyncExitStack/push.md)
