---
type: reference
title: "queue.PriorityQueue.empty"
description: "Return True if the queue is empty, False otherwise (not reliable!)."
tags: ["queue", "stdlib"]
---
# queue.PriorityQueue.empty

Return True if the queue is empty, False otherwise (not reliable!).

This method is likely to be removed at some point.  Use qsize() == 0
as a direct substitute, but be aware that either approach risks a race
condition where a queue can grow before the result of empty() or
qsize() can be used.

To create code that needs to wait for all queued tasks to be
completed, the preferred technique is to use the join() method.

## Related

- [full](/queue/PriorityQueue/full.md)
- [get](/queue/PriorityQueue/get.md)
- [get_nowait](/queue/PriorityQueue/get_nowait.md)
