---
type: reference
title: "math.isclose"
description: "Determine whether two floating-point numbers are close in value."
tags: ["math", "stdlib"]
---
# math.isclose

Determine whether two floating-point numbers are close in value.

  rel_tol
    maximum difference for being considered "close", relative to the
    magnitude of the input values
  abs_tol
    maximum difference for being considered "close", regardless of the
    magnitude of the input values

Return True if a is close in value to b, and False otherwise.

For the values to be considered close, the difference between them
must be smaller than at least one of the tolerances.

-inf, inf and NaN behave similarly to the IEEE 754 Standard.  That
is, NaN is not close to anything, even itself.  inf and -inf are
only close to themselves.

## Related

- [log1p](/math/log1p.md)
- [modf](/math/modf.md)
- [nextafter](/math/nextafter.md)
