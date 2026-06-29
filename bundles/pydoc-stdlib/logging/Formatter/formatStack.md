---
type: reference
title: "logging.Formatter.formatStack"
description: "This method is provided as an extension point for specialized"
tags: ["logging", "stdlib"]
---
# logging.Formatter.formatStack

This method is provided as an extension point for specialized
formatting of stack information.

The input data is a string as returned from a call to
:func:`traceback.print_stack`, but with the last trailing newline
removed.

The base implementation just returns the value passed in.

## Related

- [formatTime](/logging/Formatter/formatTime.md)
- [GenericAlias](/logging/GenericAlias.md)
- [Handler](/logging/Handler.md)
