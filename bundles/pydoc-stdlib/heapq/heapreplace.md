---
type: reference
title: "heapq.heapreplace"
description: "Pop and return the current smallest value, and add the new item."
tags: ["heapq", "stdlib"]
---
# heapq.heapreplace

Pop and return the current smallest value, and add the new item.

This is more efficient than heappop() followed by heappush(), and can be
more appropriate when using a fixed-size heap.  Note that the value
returned may be larger than item!  That constrains reasonable uses of
this routine unless written as part of a conditional replacement:

    if item > heap[0]:
        item = heapreplace(heap, item)

## Related

- [merge](/heapq/merge.md)
- [nlargest](/heapq/nlargest.md)
- [nsmallest](/heapq/nsmallest.md)
