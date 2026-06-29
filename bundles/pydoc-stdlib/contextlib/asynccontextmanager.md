---
type: reference
title: "contextlib.asynccontextmanager"
description: "@asynccontextmanager decorator."
tags: ["contextlib", "stdlib"]
---
# contextlib.asynccontextmanager

@asynccontextmanager decorator.

Typical usage:

    @asynccontextmanager
    async def some_async_generator(<arguments>):
        <setup>
        try:
            yield <value>
        finally:
            <cleanup>

This makes this:

    async with some_async_generator(<arguments>) as <variable>:
        <body>

equivalent to this:

    <setup>
    try:
        <variable> = <value>
        <body>
    finally:
        <cleanup>

## Related

- [closing](/contextlib/closing.md)
- [contextmanager](/contextlib/contextmanager.md)
- [deque](/contextlib/deque.md)
