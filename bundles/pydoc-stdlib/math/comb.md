---
type: reference
title: "math.comb"
description: "Number of ways to choose k items from n items without repetition and without order."
tags: ["math", "stdlib"]
---
# math.comb

Number of ways to choose k items from n items without repetition and without order.

Evaluates to n! / (k! * (n - k)!) when k <= n and evaluates
to zero when k > n.

Also called the binomial coefficient because it is equivalent
to the coefficient of k-th term in polynomial expansion of the
expression (1 + x)**n.

Raises TypeError if either of the arguments are not integers.
Raises ValueError if either of the arguments are negative.

## Related

- [copysign](/math/copysign.md)
- [dist](/math/dist.md)
- [expm1](/math/expm1.md)
