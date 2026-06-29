---
type: reference
title: "logging.Formatter.formatTime"
description: "Return the creation time of the specified LogRecord as formatted text."
tags: ["logging", "stdlib"]
---
# logging.Formatter.formatTime

Return the creation time of the specified LogRecord as formatted text.

This method should be called from format() by a formatter which
wants to make use of a formatted time. This method can be overridden
in formatters to provide for any specific requirement, but the
basic behaviour is as follows: if datefmt (a string) is specified,
it is used with time.strftime() to format the creation time of the
record. Otherwise, an ISO8601-like (or RFC 3339-like) format is used.
The resulting string is returned. This function uses a user-configurable
function to convert the creation time to a tuple. By default,
time.localtime() is used; to change this for a particular formatter
instance, set the 'converter' attribute to a function with the same
signature as time.localtime() or time.gmtime(). To change it for all
formatters, for example if you want all logging times to be shown in GMT,
set the 'converter' attribute in the Formatter class.

## Related

- [GenericAlias](/logging/GenericAlias.md)
- [Handler](/logging/Handler.md)
- [close](/logging/Handler/close.md)
