---
type: reference
title: "queue.Queue.put"
description: "Put an item into the queue."
tags: ["queue", "stdlib"]
---
# queue.Queue.put

Put an item into the queue.

If optional args 'block' is true and 'timeout' is None (the default),
block if necessary until a free slot is available. If 'timeout' is
a non-negative number, it blocks at most 'timeout' seconds and raises
the Full exception if no free slot was available within that time.
Otherwise ('block' is false), put an item on the queue if a free slot
is immediately available, else raise the Full exception ('timeout'
is ignored in that case).

## Related

- [PriorityQueue](/queue/PriorityQueue.md)
- [empty](/queue/PriorityQueue/empty.md)
- [full](/queue/PriorityQueue/full.md)
