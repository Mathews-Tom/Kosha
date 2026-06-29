---
type: reference
title: "functools.get_cache_token"
description: "Returns the current ABC cache token."
tags: ["functools", "stdlib"]
---
# functools.get_cache_token

Returns the current ABC cache token.

The token is an opaque object (supporting equality testing) identifying the
current version of the ABC cache for virtual subclasses. The token changes
with every call to register() on any ABC.

## Related

- [lru_cache](/functools/lru_cache.md)
- [namedtuple](/functools/namedtuple.md)
- [partial](/functools/partial.md)
