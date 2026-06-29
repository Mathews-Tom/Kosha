---
type: reference
title: "contextlib.AsyncExitStack.push_async_exit"
description: "Registers a coroutine function with the standard __aexit__ method"
tags: ["contextlib", "stdlib"]
---
# contextlib.AsyncExitStack.push_async_exit

Registers a coroutine function with the standard __aexit__ method
signature.

Can suppress exceptions the same way __aexit__ method can.
Also accepts any object with an __aexit__ method (registering a call
to the method instead of the object itself).

## Related

- [ExitStack](/contextlib/ExitStack.md)
- [enter_context](/contextlib/ExitStack/enter_context.md)
- [push](/contextlib/ExitStack/push.md)
