---
type: reference
title: "random.Random.betavariate"
description: "Beta distribution."
tags: ["random", "stdlib"]
---
# random.Random.betavariate

Beta distribution.

Conditions on the parameters are alpha > 0 and beta > 0.
Returned values range between 0 and 1.

The mean (expected value) and variance of the random variable are:

    E[X] = alpha / (alpha + beta)
    Var[X] = alpha * beta / ((alpha + beta)**2 * (alpha + beta + 1))

## Related

- [binomialvariate](/random/Random/binomialvariate.md)
- [choices](/random/Random/choices.md)
- [expovariate](/random/Random/expovariate.md)
