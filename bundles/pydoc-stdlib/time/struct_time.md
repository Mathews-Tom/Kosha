---
type: reference
title: "time.struct_time"
description: "The time value as returned by gmtime(), localtime(), and strptime(), and"
tags: ["time", "stdlib"]
---
# time.struct_time

The time value as returned by gmtime(), localtime(), and strptime(), and
accepted by asctime(), mktime() and strftime().  May be considered as a
sequence of 9 integers.

Note that several fields' values are not the same as those defined by
the C language standard for struct tm.  For example, the value of the
field tm_year is the actual year, not year - 1900.  See individual
fields' descriptions for details.

## Related

- [thread_time](/time/thread_time.md)
- [thread_time_ns](/time/thread_time_ns.md)
- [asctime](/time/asctime.md)
