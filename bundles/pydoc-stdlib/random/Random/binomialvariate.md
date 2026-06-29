---
type: reference
title: "random.Random.binomialvariate"
description: "Binomial random variable."
tags: ["random", "stdlib"]
---
# random.Random.binomialvariate

Binomial random variable.

Gives the number of successes for *n* independent trials
with the probability of success in each trial being *p*:

    sum(random() < p for i in range(n))

Returns an integer in the range:   0 <= X <= n

The mean (expected value) and variance of the random variable are:

    E[X] = n * p
    Var[x] = n * p * (1 - p)

## Related

- [choices](/random/Random/choices.md)
- [expovariate](/random/Random/expovariate.md)
- [gammavariate](/random/Random/gammavariate.md)
