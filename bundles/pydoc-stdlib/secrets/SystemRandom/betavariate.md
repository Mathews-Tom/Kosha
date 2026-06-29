---
type: reference
title: "secrets.SystemRandom.betavariate"
description: "Beta distribution."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.betavariate

Beta distribution.

Conditions on the parameters are alpha > 0 and beta > 0.
Returned values range between 0 and 1.

The mean (expected value) and variance of the random variable are:

    E[X] = alpha / (alpha + beta)
    Var[X] = alpha * beta / ((alpha + beta)**2 * (alpha + beta + 1))

## Related

- [binomialvariate](/secrets/SystemRandom/binomialvariate.md)
- [choices](/secrets/SystemRandom/choices.md)
- [expovariate](/secrets/SystemRandom/expovariate.md)
