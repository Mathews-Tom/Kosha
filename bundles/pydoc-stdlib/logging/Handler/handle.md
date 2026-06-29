---
type: reference
title: "logging.Handler.handle"
description: "Conditionally emit the specified logging record."
tags: ["logging", "stdlib"]
---
# logging.Handler.handle

Conditionally emit the specified logging record.

Emission depends on filters which may have been added to the handler.
Wrap the actual emission of the record with acquisition/release of
the I/O thread lock.

Returns an instance of the log record that was emitted
if it passed all filters, otherwise a false value is returned.

## Related

- [Filter](/logging/Filter.md)
- [filter](/logging/Filter/filter.md)
- [Formatter](/logging/Formatter.md)
