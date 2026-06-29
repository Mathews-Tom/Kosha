---
type: reference
title: "json.JSONDecoder.raw_decode"
description: "Decode a JSON document from ``s`` (a ``str`` beginning with"
tags: ["json", "stdlib"]
---
# json.JSONDecoder.raw_decode

Decode a JSON document from ``s`` (a ``str`` beginning with
a JSON document) and return a 2-tuple of the Python
representation and the index in ``s`` where the document ended.

This can be used to decode a JSON document from a string that may
have extraneous data at the end.

## Related

- [JSONEncoder](/json/JSONEncoder.md)
- [default](/json/JSONEncoder/default.md)
- [encode](/json/JSONEncoder/encode.md)
