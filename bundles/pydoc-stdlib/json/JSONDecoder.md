---
type: reference
title: "json.JSONDecoder"
description: "Simple JSON <https://json.org> decoder"
tags: ["json", "stdlib"]
---
# json.JSONDecoder

Simple JSON <https://json.org> decoder

Performs the following translations in decoding by default:

+---------------+-------------------+
| JSON          | Python            |
+===============+===================+
| object        | dict              |
+---------------+-------------------+
| array         | list              |
+---------------+-------------------+
| string        | str               |
+---------------+-------------------+
| number (int)  | int               |
+---------------+-------------------+
| number (real) | float             |
+---------------+-------------------+
| true          | True              |
+---------------+-------------------+
| false         | False             |
+---------------+-------------------+
| null          | None              |
+---------------+-------------------+

It also understands ``NaN``, ``Infinity``, and ``-Infinity`` as
their corresponding ``float`` values, which is outside the JSON spec.

## Related

- [decode](/json/JSONDecoder/decode.md)
- [raw_decode](/json/JSONDecoder/raw_decode.md)
- [JSONEncoder](/json/JSONEncoder.md)
