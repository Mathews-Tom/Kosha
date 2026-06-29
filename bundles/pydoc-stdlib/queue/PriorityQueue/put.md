---
type: reference
title: "queue.PriorityQueue.put"
description: "Put an item into the queue."
tags: ["queue", "stdlib"]
---
# queue.PriorityQueue.put

Put an item into the queue.

If optional args 'block' is true and 'timeout' is None (the default),
block if necessary until a free slot is available. If 'timeout' is
a non-negative number, it blocks at most 'timeout' seconds and raises
the Full exception if no free slot was available within that time.
Otherwise ('block' is false), put an item on the queue if a free slot
is immediately available, else raise the Full exception ('timeout'
is ignored in that case).

## Related

- [put_nowait](/queue/PriorityQueue/put_nowait.md)
- [task_done](/queue/PriorityQueue/task_done.md)
- [Queue](/queue/Queue.md)
