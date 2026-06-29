---
type: reference
title: "secrets.SystemRandom.randrange"
description: "Choose a random item from range(stop) or range(start, stop[, step])."
tags: ["secrets", "stdlib"]
---
# secrets.SystemRandom.randrange

Choose a random item from range(stop) or range(start, stop[, step]).

Roughly equivalent to ``choice(range(start, stop, step))`` but
supports arbitrarily large ranges and is optimized for common cases.

## Related

- [sample](/secrets/SystemRandom/sample.md)
- [triangular](/secrets/SystemRandom/triangular.md)
- [uniform](/secrets/SystemRandom/uniform.md)
