---
type: reference
title: "time.localtime"
description: "localtime([seconds]) -> (tm_year,tm_mon,tm_mday,tm_hour,tm_min,"
tags: ["time", "stdlib"]
---
# time.localtime

localtime([seconds]) -> (tm_year,tm_mon,tm_mday,tm_hour,tm_min,
                          tm_sec,tm_wday,tm_yday,tm_isdst)

Convert seconds since the Epoch to a time tuple expressing local time.
When 'seconds' is not passed in, convert the current time instead.

## Related

- [mktime](/time/mktime.md)
- [process_time](/time/process_time.md)
- [process_time_ns](/time/process_time_ns.md)
