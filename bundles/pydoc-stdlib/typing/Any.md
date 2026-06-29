---
type: reference
title: "typing.Any"
description: "Special type indicating an unconstrained type."
tags: ["typing", "stdlib"]
---
# typing.Any

Special type indicating an unconstrained type.

- Any is compatible with every type.
- Any assumed to have all methods.
- All values assumed to be instances of Any.

Note that all the above statements are true from the point of view of
static type checkers. At runtime, Any should not be used with instance
checks.

## Related

- [Generic](/typing/Generic.md)
- [GenericAlias](/typing/GenericAlias.md)
- [IO](/typing/IO.md)
