---
type: reference
title: "decimal.Context.power"
description: "Compute a**b. If 'a' is negative, then 'b' must be integral. The result"
tags: ["decimal", "stdlib"]
---
# decimal.Context.power

Compute a**b. If 'a' is negative, then 'b' must be integral. The result
will be inexact unless 'a' is integral and the result is finite and can
be expressed exactly in 'precision' digits.  In the Python version the
result is always correctly rounded, in the C version the result is almost
always correctly rounded.

If modulo is given, compute (a**b) % modulo. The following restrictions
hold:

    * all three arguments must be integral
    * 'b' must be nonnegative
    * at least one of 'a' or 'b' must be nonzero
    * modulo must be nonzero and less than 10**prec in absolute value

## Related

- [remainder](/decimal/Context/remainder.md)
- [remainder_near](/decimal/Context/remainder_near.md)
- [Decimal](/decimal/Decimal.md)
