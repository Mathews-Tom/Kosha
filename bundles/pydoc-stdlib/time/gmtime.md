---
type: reference
title: "time.gmtime"
description: "gmtime([seconds]) -> (tm_year, tm_mon, tm_mday, tm_hour, tm_min,"
tags: ["time", "stdlib"]
---
# time.gmtime

gmtime([seconds]) -> (tm_year, tm_mon, tm_mday, tm_hour, tm_min,
                       tm_sec, tm_wday, tm_yday, tm_isdst)

Convert seconds since the Epoch to a time tuple expressing UTC (a.k.a.
GMT).  When 'seconds' is not passed in, convert the current time instead.

If the platform supports the tm_gmtoff and tm_zone, they are available as
attributes only.

## Related

- [localtime](/time/localtime.md)
- [mktime](/time/mktime.md)
- [process_time](/time/process_time.md)
