---
type: reference
title: "contextlib.closing"
description: "Context to automatically close something at the end of a block."
tags: ["contextlib", "stdlib"]
---
# contextlib.closing

Context to automatically close something at the end of a block.

Code like this:

    with closing(<module>.open(<arguments>)) as f:
        <block>

is equivalent to this:

    f = <module>.open(<arguments>)
    try:
        <block>
    finally:
        f.close()

## Related

- [contextmanager](/contextlib/contextmanager.md)
- [deque](/contextlib/deque.md)
- [AsyncContextDecorator](/contextlib/AsyncContextDecorator.md)
