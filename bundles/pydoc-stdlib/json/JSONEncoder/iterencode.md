---
type: reference
title: "json.JSONEncoder.iterencode"
description: "Encode the given object and yield each string"
tags: ["json", "stdlib"]
---
# json.JSONEncoder.iterencode

Encode the given object and yield each string
representation as available.

For example::

    for chunk in JSONEncoder().iterencode(bigobject):
        mysocket.write(chunk)

## Related

- [dump](/json/dump.md)
- [dumps](/json/dumps.md)
- [load](/json/load.md)
