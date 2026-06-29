---
type: reference
title: "queue.PriorityQueue.full"
description: "Return True if the queue is full, False otherwise (not reliable!)."
tags: ["queue", "stdlib"]
---
# queue.PriorityQueue.full

Return True if the queue is full, False otherwise (not reliable!).

This method is likely to be removed at some point.  Use qsize() >= n
as a direct substitute, but be aware that either approach risks a race
condition where a queue can shrink before the result of full() or
qsize() can be used.

## Related

- [get](/queue/PriorityQueue/get.md)
- [get_nowait](/queue/PriorityQueue/get_nowait.md)
- [join](/queue/PriorityQueue/join.md)
