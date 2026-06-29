---
type: reference
title: "queue.PriorityQueue.put_nowait"
description: "Put an item into the queue without blocking."
tags: ["queue", "stdlib"]
---
# queue.PriorityQueue.put_nowait

Put an item into the queue without blocking.

Only enqueue the item if a free slot is immediately available.
Otherwise raise the Full exception.

## Related

- [task_done](/queue/PriorityQueue/task_done.md)
- [Queue](/queue/Queue.md)
- [empty](/queue/Queue/empty.md)
