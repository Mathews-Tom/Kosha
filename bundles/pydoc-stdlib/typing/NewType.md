---
type: reference
title: "typing.NewType"
description: "NewType creates simple unique types with almost zero runtime overhead."
tags: ["typing", "stdlib"]
---
# typing.NewType

NewType creates simple unique types with almost zero runtime overhead.

NewType(name, tp) is considered a subtype of tp
by static type checkers. At runtime, NewType(name, tp) returns
a dummy callable that simply returns its argument.

Usage::

    UserId = NewType('UserId', int)

    def name_by_id(user_id: UserId) -> str:
        ...

    UserId('user')          # Fails type check

    name_by_id(42)          # Fails type check
    name_by_id(UserId(42))  # OK

    num = UserId(5) + 1     # type: int

## Related

- [ParamSpec](/typing/ParamSpec.md)
- [ParamSpecArgs](/typing/ParamSpecArgs.md)
- [ParamSpecKwargs](/typing/ParamSpecKwargs.md)
