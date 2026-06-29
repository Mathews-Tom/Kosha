---
type: reference
title: "secrets.SystemRandom.triangular"
description: "Triangular distribution."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.triangular

Triangular distribution.

Continuous distribution bounded by given lower and upper limits,
and having a given mode value in-between.

http://en.wikipedia.org/wiki/Triangular_distribution

The mean (expected value) and variance of the random variable are:

    E[X] = (low + high + mode) / 3
    Var[X] = (low**2 + high**2 + mode**2 - low*high - low*mode - high*mode) / 18

## Related

- [uniform](/secrets/SystemRandom/uniform.md)
- [vonmisesvariate](/secrets/SystemRandom/vonmisesvariate.md)
- [weibullvariate](/secrets/SystemRandom/weibullvariate.md)
