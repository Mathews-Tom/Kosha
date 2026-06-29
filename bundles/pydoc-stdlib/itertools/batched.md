---
type: reference
title: "itertools.batched"
description: "Batch data into tuples of length n. The last batch may be shorter than n."
tags: ["itertools", "stdlib"]
---
# itertools.batched

Batch data into tuples of length n. The last batch may be shorter than n.

Loops over the input iterable and accumulates data into tuples
up to size n.  The input is consumed lazily, just enough to
fill a batch.  The result is yielded as soon as a batch is full
or when the input iterable is exhausted.

    >>> for batch in batched('ABCDEFG', 3):
    ...     print(batch)
    ...
    ('A', 'B', 'C')
    ('D', 'E', 'F')
    ('G',)

## Related

- [chain](/itertools/chain.md)
- [from_iterable](/itertools/chain/from_iterable.md)
- [combinations](/itertools/combinations.md)
