---
type: reference
title: "contextlib.aclosing"
description: "Async context manager for safely finalizing an asynchronously cleaned-up"
tags: ["contextlib", "stdlib"]
---
# contextlib.aclosing

Async context manager for safely finalizing an asynchronously cleaned-up
resource such as an async generator, calling its ``aclose()`` method.

Code like this:

    async with aclosing(<module>.fetch(<arguments>)) as agen:
        <block>

is equivalent to this:

    agen = <module>.fetch(<arguments>)
    try:
        <block>
    finally:
        await agen.aclose()

## Related

- [asynccontextmanager](/contextlib/asynccontextmanager.md)
- [closing](/contextlib/closing.md)
- [contextmanager](/contextlib/contextmanager.md)
