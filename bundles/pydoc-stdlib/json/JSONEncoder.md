---
type: reference
title: "json.JSONEncoder"
description: "Extensible JSON <https://json.org> encoder for Python data structures."
tags: ["json", "stdlib"]
---
# json.JSONEncoder

Extensible JSON <https://json.org> encoder for Python data structures.

Supports the following objects and types by default:

+-------------------+---------------+
| Python            | JSON          |
+===================+===============+
| dict              | object        |
+-------------------+---------------+
| list, tuple       | array         |
+-------------------+---------------+
| str               | string        |
+-------------------+---------------+
| int, float        | number        |
+-------------------+---------------+
| True              | true          |
+-------------------+---------------+
| False             | false         |
+-------------------+---------------+
| None              | null          |
+-------------------+---------------+

To extend this to recognize other objects, subclass and implement a
``.default()`` method with another method that returns a serializable
object for ``o`` if possible, otherwise it should call the superclass
implementation (to raise ``TypeError``).

## Related

- [default](/json/JSONEncoder/default.md)
- [encode](/json/JSONEncoder/encode.md)
- [iterencode](/json/JSONEncoder/iterencode.md)
