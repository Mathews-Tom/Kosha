---
type: reference
title: "collections.ChainMap.update"
description: "D.update([E, ]**F) -> None. Update D from mapping/iterable E and F."
tags: ["collections", "stdlib"]
---
# collections.ChainMap.update

D.update([E, ]**F) -> None.  Update D from mapping/iterable E and F.
If E present and has a .keys() method, does:     for k in E.keys(): D[k] = E[k]
If E present and lacks .keys() method, does:     for (k, v) in E: D[k] = v
In either case, this is followed by: for k, v in F.items(): D[k] = v

## Related

- [Counter](/collections/Counter.md)
- [elements](/collections/Counter/elements.md)
- [most_common](/collections/Counter/most_common.md)
