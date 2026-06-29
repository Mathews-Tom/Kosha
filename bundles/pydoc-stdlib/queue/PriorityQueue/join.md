---
type: reference
title: "queue.PriorityQueue.join"
description: "Blocks until all items in the Queue have been gotten and processed."
tags: ["queue", "stdlib"]
---
# queue.PriorityQueue.join

Blocks until all items in the Queue have been gotten and processed.

The count of unfinished tasks goes up whenever an item is added to the
queue. The count goes down whenever a consumer thread calls task_done()
to indicate the item was retrieved and all work on it is complete.

When the count of unfinished tasks drops to zero, join() unblocks.

## Related

- [put](/queue/PriorityQueue/put.md)
- [put_nowait](/queue/PriorityQueue/put_nowait.md)
- [task_done](/queue/PriorityQueue/task_done.md)
