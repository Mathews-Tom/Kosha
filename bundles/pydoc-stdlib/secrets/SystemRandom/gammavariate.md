---
type: reference
title: "secrets.SystemRandom.gammavariate"
description: "Gamma distribution. Not the gamma function!"
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.gammavariate

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

- [gauss](/secrets/SystemRandom/gauss.md)
- [lognormvariate](/secrets/SystemRandom/lognormvariate.md)
- [randrange](/secrets/SystemRandom/randrange.md)
