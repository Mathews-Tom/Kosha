---
type: reference
title: "ast.NodeVisitor"
description: "A node visitor base class that walks the abstract syntax tree and calls a"
tags: ["ast", "stdlib"]
---
# ast.NodeVisitor

A node visitor base class that walks the abstract syntax tree and calls a
visitor function for every node found.  This function may return a value
which is forwarded by the `visit` method.

This class is meant to be subclassed, with the subclass adding visitor
methods.

Per default the visitor functions for the nodes are ``'visit_'`` +
class name of the node.  So a `TryFinally` node visit function would
be `visit_TryFinally`.  This behavior can be changed by overriding
the `visit` method.  If no visitor function exists for a node
(return value `None`) the `generic_visit` visitor is used instead.

Don't use the `NodeVisitor` if you want to apply changes to nodes during
traversing.  For this a special visitor exists (`NodeTransformer`) that
allows modifications.

## Related

- [arguments](/ast/arguments.md)
- [contextmanager](/ast/contextmanager.md)
- [copy_location](/ast/copy_location.md)
