---
type: reference
title: "operator.attrgetter"
description: "Return a callable object that fetches the given attribute(s) from its operand."
tags: ["operator", "stdlib"]
---
# operator.attrgetter

Return a callable object that fetches the given attribute(s) from its operand.
After f = attrgetter('name'), the call f(r) returns r.name.
After g = attrgetter('name', 'date'), the call g(r) returns (r.name, r.date).
After h = attrgetter('name.first', 'name.last'), the call h(r) returns
(r.name.first, r.name.last).

## Related

- [itemgetter](/operator/itemgetter.md)
- [length_hint](/operator/length_hint.md)
- [methodcaller](/operator/methodcaller.md)
