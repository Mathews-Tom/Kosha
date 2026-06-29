---
type: reference
title: "logging.Filter"
description: "Filter instances are used to perform arbitrary filtering of LogRecords."
tags: ["logging", "stdlib"]
---
# logging.Filter

Filter instances are used to perform arbitrary filtering of LogRecords.

Loggers and Handlers can optionally use Filter instances to filter
records as desired. The base filter class only allows events which are
below a certain point in the logger hierarchy. For example, a filter
initialized with "A.B" will allow events logged by loggers "A.B",
"A.B.C", "A.B.C.D", "A.B.D" etc. but not "A.BB", "B.A.B" etc. If
initialized with the empty string, all events are passed.

## Related

- [filter](/logging/Filter/filter.md)
- [Formatter](/logging/Formatter.md)
- [converter](/logging/Formatter/converter.md)
