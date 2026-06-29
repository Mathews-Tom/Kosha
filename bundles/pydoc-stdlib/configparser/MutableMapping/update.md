---
type: reference
title: "configparser.MutableMapping.update"
description: "D.update([E, ]**F) -> None. Update D from mapping/iterable E and F."
tags: ["configparser", "stdlib"]
---
# configparser.MutableMapping.update

D.update([E, ]**F) -> None.  Update D from mapping/iterable E and F.
If E present and has a .keys() method, does:     for k in E.keys(): D[k] = E[k]
If E present and lacks .keys() method, does:     for (k, v) in E: D[k] = v
In either case, this is followed by: for k, v in F.items(): D[k] = v

## Related

- [BasicInterpolation](/configparser/BasicInterpolation.md)
- [ConverterMapping](/configparser/ConverterMapping.md)
- [pop](/configparser/ConverterMapping/pop.md)
