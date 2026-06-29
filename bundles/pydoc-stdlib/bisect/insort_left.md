---
type: reference
title: "bisect.insort_left"
description: "Insert item x in list a, and keep it sorted assuming a is sorted."
tags: ["bisect", "stdlib"]
---
# bisect.insort_left

Insert item x in list a, and keep it sorted assuming a is sorted.

If x is already in a, insert it to the left of the leftmost x.

Optional args lo (default 0) and hi (default len(a)) bound the
slice of a to be searched.

A custom key function can be supplied to customize the sort order.

## Related

- [insort_right](/bisect/insort_right.md)
- [bisect](/bisect/bisect.md)
- [bisect_left](/bisect/bisect_left.md)
