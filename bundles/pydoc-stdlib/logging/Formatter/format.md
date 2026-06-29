---
type: reference
title: "logging.Formatter.format"
description: "Format the specified record as text."
tags: ["logging", "stdlib"]
---
# logging.Formatter.format

Format the specified record as text.

The record's attribute dictionary is used as the operand to a
string formatting operation which yields the returned string.
Before formatting the dictionary, a couple of preparatory steps
are carried out. The message attribute of the record is computed
using LogRecord.getMessage(). If the formatting string uses the
time (as determined by a call to usesTime(), formatTime() is
called to format the event time. If there is exception information,
it is formatted using formatException() and appended to the message.

## Related

- [formatException](/logging/Formatter/formatException.md)
- [formatStack](/logging/Formatter/formatStack.md)
- [formatTime](/logging/Formatter/formatTime.md)
