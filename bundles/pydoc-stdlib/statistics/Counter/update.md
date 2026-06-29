---
type: reference
title: "statistics.Counter.update"
description: "Like dict.update() but add counts instead of replacing them."
tags: ["statistics", "stdlib"]
---
# statistics.Counter.update

Like dict.update() but add counts instead of replacing them.

Source can be an iterable, a dictionary, or another Counter instance.

>>> c = Counter('which')
>>> c.update('witch')           # add elements from another iterable
>>> d = Counter('watch')
>>> c.update(d)                 # add elements from another counter
>>> c['h']                      # four 'h' in which, witch, and watch
4

## Related

- [Decimal](/statistics/Decimal.md)
- [as_integer_ratio](/statistics/Decimal/as_integer_ratio.md)
- [canonical](/statistics/Decimal/canonical.md)
