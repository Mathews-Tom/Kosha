---
type: reference
title: "queue.Queue.join"
description: "Blocks until all items in the Queue have been gotten and processed."
tags: ["queue", "stdlib"]
---
# queue.Queue.join

Blocks until all items in the Queue have been gotten and processed.

The count of unfinished tasks goes up whenever an item is added to the
queue. The count goes down whenever a consumer thread calls task_done()
to indicate the item was retrieved and all work on it is complete.

When the count of unfinished tasks drops to zero, join() unblocks.

## Related

- [put](/queue/Queue/put.md)
- [PriorityQueue](/queue/PriorityQueue.md)
- [empty](/queue/PriorityQueue/empty.md)
