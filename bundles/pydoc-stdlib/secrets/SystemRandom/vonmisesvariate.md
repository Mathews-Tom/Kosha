---
type: reference
title: "secrets.SystemRandom.vonmisesvariate"
description: "Circular data distribution."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.vonmisesvariate

Circular data distribution.

mu is the mean angle, expressed in radians between 0 and 2*pi, and
kappa is the concentration parameter, which must be greater than or
equal to zero.  If kappa is equal to zero, this distribution reduces
to a uniform random angle over the range 0 to 2*pi.

## Related

- [weibullvariate](/secrets/SystemRandom/weibullvariate.md)
- [compare_digest](/secrets/compare_digest.md)
- [token_bytes](/secrets/token_bytes.md)
