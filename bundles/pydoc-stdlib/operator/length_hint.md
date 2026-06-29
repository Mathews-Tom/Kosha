---
type: reference
title: "operator.length_hint"
description: "Return an estimate of the number of items in obj."
tags: ["operator", "stdlib"]
---
# operator.length_hint

Return an estimate of the number of items in obj.

This is useful for presizing containers when building from an iterable.

If the object supports len(), the result will be exact.
Otherwise, it may over- or under-estimate by an arbitrary amount.
The result will be an integer >= 0.

## Related

- [methodcaller](/operator/methodcaller.md)
- [attrgetter](/operator/attrgetter.md)
- [itemgetter](/operator/itemgetter.md)
