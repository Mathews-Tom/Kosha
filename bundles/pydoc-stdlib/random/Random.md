---
type: reference
title: "random.Random"
description: "Random number generator base class used by bound module functions."
tags: ["random", "stdlib"]
---
# random.Random

Random number generator base class used by bound module functions.

Used to instantiate instances of Random to get generators that don't
share state.

Class Random can also be subclassed if you want to use a different basic
generator of your own devising: in that case, override the following
methods:  random(), seed(), getstate(), and setstate().
Optionally, implement a getrandbits() method so that randrange()
can cover arbitrarily large ranges.

## Related

- [betavariate](/random/Random/betavariate.md)
- [binomialvariate](/random/Random/binomialvariate.md)
- [choices](/random/Random/choices.md)
