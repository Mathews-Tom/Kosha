---
type: reference
title: "ast.contextmanager"
description: "@contextmanager decorator."
tags: ["ast", "stdlib"]
---
# ast.contextmanager

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

- [copy_location](/ast/copy_location.md)
- [dump](/ast/dump.md)
- [expr](/ast/expr.md)
