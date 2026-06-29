---
type: reference
title: "collections.ChainMap"
description: "A ChainMap groups multiple dicts (or other mappings) together"
tags: ["collections", "stdlib"]
---
# collections.ChainMap

A ChainMap groups multiple dicts (or other mappings) together
to create a single, updateable view.

The underlying mappings are stored in a list.  That list is public and can
be accessed or updated using the *maps* attribute.  There is no other
state.

Lookups search the underlying mappings successively until a key is found.
In contrast, writes, updates, and deletions only operate on the first
mapping.

## Related

- [new_child](/collections/ChainMap/new_child.md)
- [pop](/collections/ChainMap/pop.md)
- [popitem](/collections/ChainMap/popitem.md)
