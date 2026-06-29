---
type: reference
title: "bisect.insort"
description: "Insert item x in list a, and keep it sorted assuming a is sorted."
tags: ["bisect", "stdlib"]
---
# bisect.insort

Insert item x in list a, and keep it sorted assuming a is sorted.

If x is already in a, insert it to the right of the rightmost x.

Optional args lo (default 0) and hi (default len(a)) bound the
slice of a to be searched.

A custom key function can be supplied to customize the sort order.

## Related

- [insort_left](/bisect/insort_left.md)
- [insort_right](/bisect/insort_right.md)
- [bisect](/bisect/bisect.md)
