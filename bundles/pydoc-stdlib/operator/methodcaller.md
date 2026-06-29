---
type: reference
title: "operator.methodcaller"
description: "Return a callable object that calls the given method on its operand."
tags: ["operator", "stdlib"]
---
# operator.methodcaller

Return a callable object that calls the given method on its operand.
After f = methodcaller('name'), the call f(r) returns r.name().
After g = methodcaller('name', 'date', foo=1), the call g(r) returns
r.name('date', foo=1).

## Related

- [attrgetter](/operator/attrgetter.md)
- [itemgetter](/operator/itemgetter.md)
- [length_hint](/operator/length_hint.md)
