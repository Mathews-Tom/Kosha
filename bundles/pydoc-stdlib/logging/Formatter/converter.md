---
type: reference
title: "logging.Formatter.converter"
description: "localtime([seconds]) -> (tm_year,tm_mon,tm_mday,tm_hour,tm_min,"
tags: ["logging", "stdlib"]
---
# logging.Formatter.converter

localtime([seconds]) -> (tm_year,tm_mon,tm_mday,tm_hour,tm_min,
                          tm_sec,tm_wday,tm_yday,tm_isdst)

Convert seconds since the Epoch to a time tuple expressing local time.
When 'seconds' is not passed in, convert the current time instead.

## Related

- [format](/logging/Formatter/format.md)
- [formatException](/logging/Formatter/formatException.md)
- [formatStack](/logging/Formatter/formatStack.md)
