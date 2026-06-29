# ast

* [ast.AsyncFor](/ast/AsyncFor.md) - AsyncFor(expr target, expr iter, stmt* body, stmt* orelse, string? type_comment)
* [ast.AsyncFunctionDef](/ast/AsyncFunctionDef.md) - AsyncFunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment, type_param* type_params)
* [ast.ClassDef](/ast/ClassDef.md) - ClassDef(identifier name, expr* bases, keyword* keywords, stmt* body, expr* decorator_list, type_param* type_params)
* [ast.FunctionDef](/ast/FunctionDef.md) - FunctionDef(identifier name, arguments args, stmt* body, expr* decorator_list, expr? returns, string? type_comment, type_param* type_params)
* [ast.MatchClass](/ast/MatchClass.md) - MatchClass(expr cls, pattern* patterns, identifier* kwd_attrs, pattern* kwd_patterns)
* [ast.NodeTransformer](/ast/NodeTransformer.md) - A :class:`NodeVisitor` subclass that walks the abstract syntax tree and
* [ast.NodeVisitor](/ast/NodeVisitor.md) - A node visitor base class that walks the abstract syntax tree and calls a
* [ast.arguments](/ast/arguments.md) - arguments(arg* posonlyargs, arg* args, arg? vararg, arg* kwonlyargs, expr* kw_defaults, arg? kwarg, expr* defaults)
* [ast.contextmanager](/ast/contextmanager.md) - @contextmanager decorator.
* [ast.copy_location](/ast/copy_location.md) - Copy source location (`lineno`, `col_offset`, `end_lineno`, and `end_col_offset`
* [ast.dump](/ast/dump.md) - Return a formatted dump of the tree in node. This is mainly useful for
* [ast.expr](/ast/expr.md) - expr = BoolOp(boolop op, expr* values)
* [ast.fix_missing_locations](/ast/fix_missing_locations.md) - When you compile a node tree with compile(), the compiler expects lineno and
* [ast.get_docstring](/ast/get_docstring.md) - Return the docstring for the given node or None if no docstring can
* [ast.get_source_segment](/ast/get_source_segment.md) - Get source code segment of the *source* that generated *node*.
* [ast.increment_lineno](/ast/increment_lineno.md) - Increment the line number and end line number of each node in the tree
