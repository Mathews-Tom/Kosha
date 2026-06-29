---
type: reference
title: "json.JSONEncoder.encode"
description: "Return a JSON string representation of a Python data structure."
tags: ["json", "stdlib"]
---
# json.JSONEncoder.encode

Return a JSON string representation of a Python data structure.

>>> from json.encoder import JSONEncoder
>>> JSONEncoder().encode({"foo": ["bar", "baz"]})
'{"foo": ["bar", "baz"]}'

## Related

- [iterencode](/json/JSONEncoder/iterencode.md)
- [dump](/json/dump.md)
- [dumps](/json/dumps.md)
