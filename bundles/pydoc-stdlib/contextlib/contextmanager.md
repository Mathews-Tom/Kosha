---
type: reference
title: "contextlib.contextmanager"
description: "@contextmanager decorator."
tags: ["contextlib", "stdlib"]
---
# contextlib.contextmanager

@contextmanager decorator.

Typical usage:

    @contextmanager
    def some_generator(<arguments>):
        <setup>
        try:
            yield <value>
        finally:
            <cleanup>

This makes this:

    with some_generator(<arguments>) as <variable>:
        <body>

equivalent to this:

    <setup>
    try:
        <variable> = <value>
        <body>
    finally:
        <cleanup>

## Related

- [deque](/contextlib/deque.md)
- [AsyncContextDecorator](/contextlib/AsyncContextDecorator.md)
- [AsyncExitStack](/contextlib/AsyncExitStack.md)
