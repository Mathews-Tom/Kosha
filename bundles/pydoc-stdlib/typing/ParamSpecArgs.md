---
type: reference
title: "typing.ParamSpecArgs"
description: "The args for a ParamSpec object."
tags: ["typing", "stdlib"]
---
# typing.ParamSpecArgs

The args for a ParamSpec object.

Given a ParamSpec object P, P.args is an instance of ParamSpecArgs.

ParamSpecArgs objects have a reference back to their ParamSpec::

    >>> P = ParamSpec("P")
    >>> P.args.__origin__ is P
    True

This type is meant for runtime introspection and has no special meaning
to static type checkers.

## Related

- [ParamSpecKwargs](/typing/ParamSpecKwargs.md)
- [Protocol](/typing/Protocol.md)
- [Text](/typing/Text.md)
