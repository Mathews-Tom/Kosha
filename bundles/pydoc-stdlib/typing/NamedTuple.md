---
type: reference
title: "typing.NamedTuple"
description: "Typed version of namedtuple."
tags: ["typing", "stdlib"]
---
# typing.NamedTuple

Typed version of namedtuple.

Usage::

    class Employee(NamedTuple):
        name: str
        id: int

This is equivalent to::

    Employee = collections.namedtuple('Employee', ['name', 'id'])

The resulting class has an extra __annotations__ attribute, giving a
dict that maps field names to types.  (The field names are also in
the _fields attribute, which is part of the namedtuple API.)
An alternative equivalent functional syntax is also accepted::

    Employee = NamedTuple('Employee', [('name', str), ('id', int)])

## Related

- [NewType](/typing/NewType.md)
- [ParamSpec](/typing/ParamSpec.md)
- [ParamSpecArgs](/typing/ParamSpecArgs.md)
