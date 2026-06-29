---
type: reference
title: "contextlib.ExitStack.push"
description: "Registers a callback with the standard __exit__ method signature."
tags: ["contextlib", "stdlib"]
---
# contextlib.ExitStack.push

Registers a callback with the standard __exit__ method signature.

Can suppress exceptions the same way __exit__ method can.
Also accepts any object with an __exit__ method (registering a call
to the method instead of the object itself).

## Related

- [GenericAlias](/contextlib/GenericAlias.md)
- [aclosing](/contextlib/aclosing.md)
- [asynccontextmanager](/contextlib/asynccontextmanager.md)
