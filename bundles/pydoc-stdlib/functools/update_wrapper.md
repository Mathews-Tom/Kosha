---
type: reference
title: "functools.update_wrapper"
description: "Update a wrapper function to look like the wrapped function"
tags: ["functools", "stdlib"]
---
# functools.update_wrapper

Update a wrapper function to look like the wrapped function

wrapper is the function to be updated
wrapped is the original function
assigned is a tuple naming the attributes assigned directly
from the wrapped function to the wrapper function (defaults to
functools.WRAPPER_ASSIGNMENTS)
updated is a tuple naming the attributes of the wrapper that
are updated with the corresponding attribute from the wrapped
function (defaults to functools.WRAPPER_UPDATES)

## Related

- [wraps](/functools/wraps.md)
- [GenericAlias](/functools/GenericAlias.md)
- [cmp_to_key](/functools/cmp_to_key.md)
