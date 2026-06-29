---
type: reference
title: "json.JSONEncoder.default"
description: "Implement this method in a subclass such that it returns"
tags: ["json", "stdlib"]
---
# json.JSONEncoder.default

Implement this method in a subclass such that it returns
a serializable object for ``o``, or calls the base implementation
(to raise a ``TypeError``).

For example, to support arbitrary iterators, you could
implement default like this::

    def default(self, o):
        try:
            iterable = iter(o)
        except TypeError:
            pass
        else:
            return list(iterable)
        # Let the base class default method raise the TypeError
        return super().default(o)

## Related

- [encode](/json/JSONEncoder/encode.md)
- [iterencode](/json/JSONEncoder/iterencode.md)
- [dump](/json/dump.md)
