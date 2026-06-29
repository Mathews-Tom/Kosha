---
type: reference
title: "itertools.count"
description: "Return a count object whose .__next__() method returns consecutive values."
tags: ["itertools", "stdlib"]
---
# itertools.count

Return a count object whose .__next__() method returns consecutive values.

Equivalent to:
    def count(firstval=0, step=1):
        x = firstval
        while 1:
            yield x
            x += step

## Related

- [cycle](/itertools/cycle.md)
- [dropwhile](/itertools/dropwhile.md)
- [filterfalse](/itertools/filterfalse.md)
