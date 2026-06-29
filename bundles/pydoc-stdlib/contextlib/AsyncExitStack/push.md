---
type: reference
title: "contextlib.AsyncExitStack.push"
description: "Registers a callback with the standard __exit__ method signature."
tags: ["contextlib", "stdlib"]
---
# contextlib.AsyncExitStack.push

Registers a callback with the standard __exit__ method signature.

Can suppress exceptions the same way __exit__ method can.
Also accepts any object with an __exit__ method (registering a call
to the method instead of the object itself).

## Related

- [push_async_callback](/contextlib/AsyncExitStack/push_async_callback.md)
- [push_async_exit](/contextlib/AsyncExitStack/push_async_exit.md)
- [ExitStack](/contextlib/ExitStack.md)
