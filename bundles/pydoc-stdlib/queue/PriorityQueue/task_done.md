---
type: reference
title: "queue.PriorityQueue.task_done"
description: "Indicate that a formerly enqueued task is complete."
tags: ["queue", "stdlib"]
---
# queue.PriorityQueue.task_done

Indicate that a formerly enqueued task is complete.

Used by Queue consumer threads.  For each get() used to fetch a task,
a subsequent call to task_done() tells the queue that the processing
on the task is complete.

If a join() is currently blocking, it will resume when all items
have been processed (meaning that a task_done() call was received
for every item that had been put() into the queue).

Raises a ValueError if called more times than there were items
placed in the queue.

## Related

- [Queue](/queue/Queue.md)
- [empty](/queue/Queue/empty.md)
- [full](/queue/Queue/full.md)
