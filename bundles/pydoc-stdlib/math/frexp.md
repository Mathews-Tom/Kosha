---
type: reference
title: "math.frexp"
description: "Return the mantissa and exponent of x, as pair (m, e)."
tags: ["math", "stdlib"]
---
# math.frexp

Return the mantissa and exponent of x, as pair (m, e).

m is a float and e is an int, such that x = m * 2.**e.
If x is 0, m and e are both 0.  Else 0.5 <= abs(m) < 1.0.

## Related

- [fsum](/math/fsum.md)
- [hypot](/math/hypot.md)
- [isclose](/math/isclose.md)
