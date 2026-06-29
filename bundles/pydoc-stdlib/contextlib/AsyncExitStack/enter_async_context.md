---
type: reference
title: "contextlib.AsyncExitStack.enter_async_context"
description: "Enters the supplied async context manager."
tags: ["contextlib", "stdlib"]
---
# contextlib.AsyncExitStack.enter_async_context

Enters the supplied async context manager.

If successful, also pushes its __aexit__ method as a callback and
returns the result of the __aenter__ method.

## Related

- [enter_context](/contextlib/AsyncExitStack/enter_context.md)
- [push](/contextlib/AsyncExitStack/push.md)
- [push_async_callback](/contextlib/AsyncExitStack/push_async_callback.md)
