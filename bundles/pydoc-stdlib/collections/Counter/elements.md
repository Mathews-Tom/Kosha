---
type: reference
title: "collections.Counter.elements"
description: "Iterator over elements repeating each as many times as its count."
tags: ["collections", "stdlib"]
---
# collections.Counter.elements

Iterator over elements repeating each as many times as its count.

>>> c = Counter('ABCABC')
>>> sorted(c.elements())
['A', 'A', 'B', 'B', 'C', 'C']

Knuth's example for prime factors of 1836:  2**2 * 3**3 * 17**1

>>> import math
>>> prime_factors = Counter({2: 2, 3: 3, 17: 1})
>>> math.prod(prime_factors.elements())
1836

Note, if an element's count has been set to zero or is a negative
number, elements() will ignore it.

## Related

- [most_common](/collections/Counter/most_common.md)
- [pop](/collections/Counter/pop.md)
- [popitem](/collections/Counter/popitem.md)
