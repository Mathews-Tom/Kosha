---
type: reference
title: "json.JSONDecodeError"
description: "Subclass of ValueError with the following additional properties:"
tags: ["json", "stdlib"]
---
# json.JSONDecodeError

Subclass of ValueError with the following additional properties:

msg: The unformatted error message
doc: The JSON document being parsed
pos: The start index of doc where parsing failed
lineno: The line corresponding to pos
colno: The column corresponding to pos

## Related

- [JSONDecoder](/json/JSONDecoder.md)
- [decode](/json/JSONDecoder/decode.md)
- [raw_decode](/json/JSONDecoder/raw_decode.md)
