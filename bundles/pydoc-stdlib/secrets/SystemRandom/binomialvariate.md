---
type: reference
title: "secrets.SystemRandom.binomialvariate"
description: "Binomial random variable."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.binomialvariate

Binomial random variable.

Gives the number of successes for *n* independent trials
with the probability of success in each trial being *p*:

    sum(random() < p for i in range(n))

Returns an integer in the range:   0 <= X <= n

The mean (expected value) and variance of the random variable are:

    E[X] = n * p
    Var[x] = n * p * (1 - p)

## Related

- [choices](/secrets/SystemRandom/choices.md)
- [expovariate](/secrets/SystemRandom/expovariate.md)
- [gammavariate](/secrets/SystemRandom/gammavariate.md)
