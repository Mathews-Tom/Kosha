---
type: reference
title: "math.hypot"
description: "hypot(*coordinates) -> value"
tags: ["math", "stdlib"]
---
# math.hypot

hypot(*coordinates) -> value

Multidimensional Euclidean distance from the origin to a point.

Roughly equivalent to:
    sqrt(sum(x**2 for x in coordinates))

For a two dimensional point (x, y), gives the hypotenuse
using the Pythagorean theorem:  sqrt(x*x + y*y).

For example, the hypotenuse of a 3/4/5 right triangle is:

    >>> hypot(3.0, 4.0)
    5.0

## Related

- [isclose](/math/isclose.md)
- [log1p](/math/log1p.md)
- [modf](/math/modf.md)
