---
type: reference
title: "logging.Handler.filter"
description: "Determine if a record is loggable by consulting all the filters."
tags: ["logging", "stdlib"]
---
# logging.Handler.filter

Determine if a record is loggable by consulting all the filters.

The default is to allow the record to be logged; any filter can veto
this by returning a false value.
If a filter attached to a handler returns a log record instance,
then that instance is used in place of the original log record in
any further processing of the event by that handler.
If a filter returns any other true value, the original log record
is used in any further processing of the event by that handler.

If none of the filters return false values, this method returns
a log record.
If any of the filters return a false value, this method returns
a false value.

.. versionchanged:: 3.2

   Allow filters to be just callables.

.. versionchanged:: 3.12
   Allow filters to return a LogRecord instead of
   modifying it in place.

## Related

- [flush](/logging/Handler/flush.md)
- [format](/logging/Handler/format.md)
- [handle](/logging/Handler/handle.md)
