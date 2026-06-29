---
type: reference
title: "ast.expr"
description: "expr = BoolOp(boolop op, expr* values)"
tags: ["ast", "stdlib"]
---
# ast.expr

expr = BoolOp(boolop op, expr* values)
| NamedExpr(expr target, expr value)
| BinOp(expr left, operator op, expr right)
| UnaryOp(unaryop op, expr operand)
| Lambda(arguments args, expr body)
| IfExp(expr test, expr body, expr orelse)
| Dict(expr* keys, expr* values)
| Set(expr* elts)
| ListComp(expr elt, comprehension* generators)
| SetComp(expr elt, comprehension* generators)
| DictComp(expr key, expr value, comprehension* generators)
| GeneratorExp(expr elt, comprehension* generators)
| Await(expr value)
| Yield(expr? value)
| YieldFrom(expr value)
| Compare(expr left, cmpop* ops, expr* comparators)
| Call(expr func, expr* args, keyword* keywords)
| FormattedValue(expr value, int conversion, expr? format_spec)
| JoinedStr(expr* values)
| Constant(constant value, string? kind)
| Attribute(expr value, identifier attr, expr_context ctx)
| Subscript(expr value, expr slice, expr_context ctx)
| Starred(expr value, expr_context ctx)
| Name(identifier id, expr_context ctx)
| List(expr* elts, expr_context ctx)
| Tuple(expr* elts, expr_context ctx)
| Slice(expr? lower, expr? upper, expr? step)

## Related

- [fix_missing_locations](/ast/fix_missing_locations.md)
- [get_docstring](/ast/get_docstring.md)
- [get_source_segment](/ast/get_source_segment.md)
