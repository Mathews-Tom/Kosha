---
type: reference
title: "math.dist"
description: "Return the Euclidean distance between two points p and q."
tags: ["math", "stdlib"]
---
# math.dist

Return the Euclidean distance between two points p and q.

The points should be specified as sequences (or iterables) of
coordinates.  Both inputs must have the same dimension.

Roughly equivalent to:
    sqrt(sum((px - qx) ** 2.0 for px, qx in zip(p, q)))

## Related

- [expm1](/math/expm1.md)
- [frexp](/math/frexp.md)
- [fsum](/math/fsum.md)
