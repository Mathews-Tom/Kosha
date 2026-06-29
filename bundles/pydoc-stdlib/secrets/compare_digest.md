---
type: reference
title: "secrets.compare_digest"
description: "Return 'a == b'."
tags: ["secrets", "stdlib"]
---
# secrets.compare_digest

Return 'a == b'.

This function uses an approach designed to prevent
timing analysis, making it appropriate for cryptography.

a and b must both be of the same type: either str (ASCII only),
or any bytes-like object.

Note: If a and b are of different lengths, or if an error occurs,
a timing attack could theoretically reveal information about the
types and lengths of a and b--but not their values.

## Related

- [token_bytes](/secrets/token_bytes.md)
- [SystemRandom](/secrets/SystemRandom.md)
- [betavariate](/secrets/SystemRandom/betavariate.md)
