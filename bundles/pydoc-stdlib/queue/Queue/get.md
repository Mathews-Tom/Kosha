---
type: reference
title: "queue.Queue.get"
description: "Remove and return an item from the queue."
tags: ["queue", "stdlib"]
---
# queue.Queue.get

Remove and return an item from the queue.

If optional args 'block' is true and 'timeout' is None (the default),
block if necessary until an item is available. If 'timeout' is
a non-negative number, it blocks at most 'timeout' seconds and raises
the Empty exception if no item was available within that time.
Otherwise ('block' is false), return an item if one is immediately
available, else raise the Empty exception ('timeout' is ignored
in that case).

## Related

- [get_nowait](/queue/Queue/get_nowait.md)
- [join](/queue/Queue/join.md)
- [put](/queue/Queue/put.md)
