---
type: reference
title: "secrets.SystemRandom.gauss"
description: "Gaussian distribution."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.gauss

Gaussian distribution.

mu is the mean, and sigma is the standard deviation.  This is
slightly faster than the normalvariate() function.

Not thread-safe without a lock around calls.

## Related

- [lognormvariate](/secrets/SystemRandom/lognormvariate.md)
- [randrange](/secrets/SystemRandom/randrange.md)
- [sample](/secrets/SystemRandom/sample.md)
