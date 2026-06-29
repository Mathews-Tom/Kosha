---
type: reference
title: "random.Random.gammavariate"
description: "Gamma distribution. Not the gamma function!"
tags: ["random", "stdlib"]
---
# random.Random.gammavariate

Gamma distribution.  Not the gamma function!

Conditions on the parameters are alpha > 0 and beta > 0.

The probability distribution function is:

            x ** (alpha - 1) * math.exp(-x / beta)
  pdf(x) =  --------------------------------------
              math.gamma(alpha) * beta ** alpha

The mean (expected value) and variance of the random variable are:

    E[X] = alpha * beta
    Var[X] = alpha * beta ** 2

## Related

- [gauss](/random/Random/gauss.md)
- [lognormvariate](/random/Random/lognormvariate.md)
- [randrange](/random/Random/randrange.md)
