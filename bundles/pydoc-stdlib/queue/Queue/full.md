---
type: reference
title: "queue.Queue.full"
description: "Return True if the queue is full, False otherwise (not reliable!)."
tags: ["queue", "stdlib"]
---
# queue.Queue.full

Return True if the queue is full, False otherwise (not reliable!).

This method is likely to be removed at some point.  Use qsize() >= n
as a direct substitute, but be aware that either approach risks a race
condition where a queue can shrink before the result of full() or
qsize() can be used.

## Related

- [get](/queue/Queue/get.md)
- [get_nowait](/queue/Queue/get_nowait.md)
- [join](/queue/Queue/join.md)
