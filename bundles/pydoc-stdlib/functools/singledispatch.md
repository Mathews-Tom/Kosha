---
type: reference
title: "functools.singledispatch"
description: "Single-dispatch generic function decorator."
tags: ["functools", "stdlib"]
---
# functools.singledispatch

Single-dispatch generic function decorator.

Transforms a function into a generic function, which can have different
behaviours depending upon the type of its first argument. The decorated
function acts as the default implementation, and additional
implementations can be registered using the register() attribute of the
generic function.

## Related

- [singledispatchmethod](/functools/singledispatchmethod.md)
- [register](/functools/singledispatchmethod/register.md)
- [update_wrapper](/functools/update_wrapper.md)
