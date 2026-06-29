---
type: reference
title: "math.perm"
description: "Number of ways to choose k items from n items without repetition and with order."
tags: ["math", "stdlib"]
---
# math.perm

Number of ways to choose k items from n items without repetition and with order.

Evaluates to n! / (n - k)! when k <= n and evaluates
to zero when k > n.

If k is not specified or is None, then k defaults to n
and the function returns n!.

Raises TypeError if either of the arguments are not integers.
Raises ValueError if either of the arguments are negative.

## Related

- [acos](/math/acos.md)
- [asin](/math/asin.md)
- [atan](/math/atan.md)
