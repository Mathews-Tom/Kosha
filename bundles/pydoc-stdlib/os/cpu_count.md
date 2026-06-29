---
type: reference
title: "os.cpu_count"
description: "Return the number of CPUs in the system; return None if indeterminable."
tags: ["os", "stdlib"]
---
# os.cpu_count

Return the number of CPUs in the system; return None if indeterminable.

This number is not equivalent to the number of CPUs the current process can
use.  The number of usable CPUs can be obtained with
``len(os.sched_getaffinity(0))``

## Related

- [device_encoding](/os/device_encoding.md)
- [execl](/os/execl.md)
- [GenericAlias](/os/GenericAlias.md)
