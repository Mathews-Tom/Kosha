---
type: reference
title: "typing.ParamSpecKwargs"
description: "The kwargs for a ParamSpec object."
tags: ["typing", "stdlib"]
---
# typing.ParamSpecKwargs

The kwargs for a ParamSpec object.

Given a ParamSpec object P, P.kwargs is an instance of ParamSpecKwargs.

ParamSpecKwargs objects have a reference back to their ParamSpec::

    >>> P = ParamSpec("P")
    >>> P.kwargs.__origin__ is P
    True

This type is meant for runtime introspection and has no special meaning
to static type checkers.

## Related

- [Protocol](/typing/Protocol.md)
- [Text](/typing/Text.md)
- [capitalize](/typing/Text/capitalize.md)
