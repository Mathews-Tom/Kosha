---
type: reference
title: "random.Random.seed"
description: "Initialize internal state from a seed."
tags: ["random", "stdlib"]
---
# random.Random.seed

Initialize internal state from a seed.

The only supported seed types are None, int, float,
str, bytes, and bytearray.

None or no argument seeds from current time or from an operating
system specific randomness source if available.

If *a* is an int, all bits are used.

For version 2 (the default), all of the bits are used if *a* is a str,
bytes, or bytearray.  For version 1 (provided for reproducing random
sequences from older versions of Python), the algorithm for str and
bytes generates a narrower range of seeds.

## Related

- [triangular](/random/Random/triangular.md)
- [uniform](/random/Random/uniform.md)
- [vonmisesvariate](/random/Random/vonmisesvariate.md)
