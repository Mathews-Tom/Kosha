---
type: reference
title: "json.load"
description: "Deserialize ``fp`` (a ``.read()``-supporting file-like object containing"
tags: ["json", "stdlib"]
---
# json.load

Deserialize ``fp`` (a ``.read()``-supporting file-like object containing
a JSON document) to a Python object.

``object_hook`` is an optional function that will be called with the
result of any object literal decode (a ``dict``). The return value of
``object_hook`` will be used instead of the ``dict``. This feature
can be used to implement custom decoders (e.g. JSON-RPC class hinting).

``object_pairs_hook`` is an optional function that will be called with the
result of any object literal decoded with an ordered list of pairs.  The
return value of ``object_pairs_hook`` will be used instead of the ``dict``.
This feature can be used to implement custom decoders.  If ``object_hook``
is also defined, the ``object_pairs_hook`` takes priority.

To use a custom ``JSONDecoder`` subclass, specify it with the ``cls``
kwarg; otherwise ``JSONDecoder`` is used.

## Related

- [loads](/json/loads.md)
- [JSONDecodeError](/json/JSONDecodeError.md)
- [JSONDecoder](/json/JSONDecoder.md)
