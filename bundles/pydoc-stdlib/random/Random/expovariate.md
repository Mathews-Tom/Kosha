---
type: reference
title: "random.Random.expovariate"
description: "Exponential distribution."
tags: ["random", "stdlib"]
---
# random.Random.expovariate

Exponential distribution.

lambd is 1.0 divided by the desired mean.  It should be
nonzero.  (The parameter would be called "lambda", but that is
a reserved word in Python.)  Returned values range from 0 to
positive infinity if lambd is positive, and from negative
infinity to 0 if lambd is negative.

The mean (expected value) and variance of the random variable are:

    E[X] = 1 / lambd
    Var[X] = 1 / lambd ** 2

## Related

- [gammavariate](/random/Random/gammavariate.md)
- [gauss](/random/Random/gauss.md)
- [lognormvariate](/random/Random/lognormvariate.md)
