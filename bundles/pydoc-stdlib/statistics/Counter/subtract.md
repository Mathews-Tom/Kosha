---
type: reference
title: "statistics.Counter.subtract"
description: "Like dict.update() but subtracts counts instead of replacing them."
tags: ["statistics", "stdlib"]
---
# statistics.Counter.subtract

Like dict.update() but subtracts counts instead of replacing them.
Counts can be reduced below zero.  Both the inputs and outputs are
allowed to contain zero and negative counts.

Source can be an iterable, a dictionary, or another Counter instance.

>>> c = Counter('which')
>>> c.subtract('witch')             # subtract elements from another iterable
>>> c.subtract(Counter('watch'))    # subtract elements from another counter
>>> c['h']                          # 2 in which, minus 1 in witch, minus 1 in watch
0
>>> c['w']                          # 1 in which, minus 1 in witch, minus 1 in watch
-1

## Related

- [update](/statistics/Counter/update.md)
- [Decimal](/statistics/Decimal.md)
- [as_integer_ratio](/statistics/Decimal/as_integer_ratio.md)
