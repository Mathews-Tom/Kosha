---
type: reference
title: "hashlib.file_digest"
description: "Hash the contents of a file-like object. Returns a digest object."
tags: ["hashlib", "stdlib"]
---
# hashlib.file_digest

Hash the contents of a file-like object. Returns a digest object.

*fileobj* must be a file-like object opened for reading in binary mode.
It accepts file objects from open(), io.BytesIO(), and SocketIO objects.
The function may bypass Python's I/O and use the file descriptor *fileno*
directly.

*digest* must either be a hash algorithm name as a *str*, a hash
constructor, or a callable that returns a hash object.

## Related

- [new](/hashlib/new.md)
- [pbkdf2_hmac](/hashlib/pbkdf2_hmac.md)
