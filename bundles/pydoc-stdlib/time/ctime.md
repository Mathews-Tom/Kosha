---
type: reference
title: "time.ctime"
description: "ctime(seconds) -> string"
tags: ["time", "stdlib"]
---
# time.ctime

ctime(seconds) -> string

Convert a time in seconds since the Epoch to a string in local time.
This is equivalent to asctime(localtime(seconds)). When the time tuple is
not present, current time as returned by localtime() is used.

## Related

- [gmtime](/time/gmtime.md)
- [localtime](/time/localtime.md)
- [mktime](/time/mktime.md)
