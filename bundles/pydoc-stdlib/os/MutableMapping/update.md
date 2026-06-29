---
type: reference
title: "os.MutableMapping.update"
description: "D.update([E, ]**F) -> None. Update D from mapping/iterable E and F."
tags: ["os", "stdlib"]
---
# os.MutableMapping.update

D.update([E, ]**F) -> None.  Update D from mapping/iterable E and F.
If E present and has a .keys() method, does:     for k in E.keys(): D[k] = E[k]
If E present and lacks .keys() method, does:     for (k, v) in E: D[k] = v
In either case, this is followed by: for k, v in F.items(): D[k] = v

## Related

- [WIFCONTINUED](/os/WIFCONTINUED.md)
- [abort](/os/abort.md)
- [access](/os/access.md)
