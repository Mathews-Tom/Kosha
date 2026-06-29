---
type: reference
title: "time.mktime"
description: "mktime(tuple) -> floating-point number"
tags: ["time", "stdlib"]
---
# time.mktime

mktime(tuple) -> floating-point number

Convert a time tuple in local time to seconds since the Epoch.
Note that mktime(gmtime(0)) will not generally return zero for most
time zones; instead the returned value will either be equal to that
of the timezone or altzone attributes on the time module.

## Related

- [process_time](/time/process_time.md)
- [process_time_ns](/time/process_time_ns.md)
- [sleep](/time/sleep.md)
