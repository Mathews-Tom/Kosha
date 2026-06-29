---
type: reference
title: "logging.Handler.close"
description: "Tidy up any resources used by the handler."
tags: ["logging", "stdlib"]
---
# logging.Handler.close

Tidy up any resources used by the handler.

This version removes the handler from an internal map of handlers,
_handlers, which is used for handler lookup by name. Subclasses
should ensure that this gets called from overridden close()
methods.

## Related

- [emit](/logging/Handler/emit.md)
- [filter](/logging/Handler/filter.md)
- [flush](/logging/Handler/flush.md)
