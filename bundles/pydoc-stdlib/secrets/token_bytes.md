---
type: reference
title: "secrets.token_bytes"
description: "Return a random byte string containing *nbytes* bytes."
tags: ["secrets", "stdlib"]
---
# secrets.token_bytes

Return a random byte string containing *nbytes* bytes.

If *nbytes* is ``None`` or not supplied, a reasonable
default is used.

>>> token_bytes(16)  #doctest:+SKIP
b'\xebr\x17D*t\xae\xd4\xe3S\xb6\xe2\xebP1\x8b'

## Related

- [SystemRandom](/secrets/SystemRandom.md)
- [betavariate](/secrets/SystemRandom/betavariate.md)
- [binomialvariate](/secrets/SystemRandom/binomialvariate.md)
