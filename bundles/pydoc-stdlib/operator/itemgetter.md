---
type: reference
title: "operator.itemgetter"
description: "Return a callable object that fetches the given item(s) from its operand."
tags: ["operator", "stdlib"]
---
# operator.itemgetter

Return a callable object that fetches the given item(s) from its operand.
After f = itemgetter(2), the call f(r) returns r[2].
After g = itemgetter(2, 5, 3), the call g(r) returns (r[2], r[5], r[3])

## Related

- [length_hint](/operator/length_hint.md)
- [methodcaller](/operator/methodcaller.md)
- [attrgetter](/operator/attrgetter.md)
