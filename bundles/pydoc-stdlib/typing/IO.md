---
type: reference
title: "typing.IO"
description: "Generic base class for TextIO and BinaryIO."
tags: ["typing", "stdlib"]
---
# typing.IO

Generic base class for TextIO and BinaryIO.

This is an abstract, generic version of the return of open().

NOTE: This does not distinguish between the different possible
classes (text vs. binary, read vs. write vs. read/write,
append-only, unbuffered).  The TextIO and BinaryIO subclasses
below capture the distinctions between text vs. binary, which is
pervasive in the interface; however we currently do not offer a
way to track the other distinctions in the type system.

## Related

- [NamedTuple](/typing/NamedTuple.md)
- [NewType](/typing/NewType.md)
- [ParamSpec](/typing/ParamSpec.md)
