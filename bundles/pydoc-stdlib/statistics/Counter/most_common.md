---
type: reference
title: "statistics.Counter.most_common"
description: "List the n most common elements and their counts from the most"
tags: ["statistics", "stdlib"]
---
# statistics.Counter.most_common

List the n most common elements and their counts from the most
common to the least.  If n is None, then list all element counts.

>>> Counter('abracadabra').most_common(3)
[('a', 5), ('b', 2), ('r', 2)]

## Related

- [pop](/statistics/Counter/pop.md)
- [popitem](/statistics/Counter/popitem.md)
- [setdefault](/statistics/Counter/setdefault.md)
