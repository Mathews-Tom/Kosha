---
type: reference
title: "secrets.SystemRandom.uniform"
description: "Get a random number in the range [a, b) or [a, b] depending on rounding."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.uniform

Get a random number in the range [a, b) or [a, b] depending on rounding.

The mean (expected value) and variance of the random variable are:

    E[X] = (a + b) / 2
    Var[X] = (b - a) ** 2 / 12

## Related

- [vonmisesvariate](/secrets/SystemRandom/vonmisesvariate.md)
- [weibullvariate](/secrets/SystemRandom/weibullvariate.md)
- [compare_digest](/secrets/compare_digest.md)
