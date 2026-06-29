---
type: reference
title: "logging.Handler"
description: "Handler instances dispatch logging events to specific destinations."
tags: ["logging", "stdlib"]
---
# logging.Handler

Handler instances dispatch logging events to specific destinations.

The base handler class. Acts as a placeholder which defines the Handler
interface. Handlers can optionally use Formatter instances to format
records as desired. By default, no formatter is specified; in this case,
the 'raw' message as determined by record.message is logged.

## Related

- [close](/logging/Handler/close.md)
- [emit](/logging/Handler/emit.md)
- [filter](/logging/Handler/filter.md)
