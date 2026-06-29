---
type: reference
title: "urllib.parse.parse_qs"
description: "Parse a query given as a string argument."
tags: ["urllib.parse", "stdlib"]
---
# urllib.parse.parse_qs

Parse a query given as a string argument.

Arguments:

qs: percent-encoded query string to be parsed

keep_blank_values: flag indicating whether blank values in
    percent-encoded queries should be treated as blank strings.
    A true value indicates that blanks should be retained as
    blank strings.  The default false value indicates that
    blank values are to be ignored and treated as if they were
    not included.

strict_parsing: flag indicating what to do with parsing errors.
    If false (the default), errors are silently ignored.
    If true, errors raise a ValueError exception.

encoding and errors: specify how to decode percent-encoded sequences
    into Unicode characters, as accepted by the bytes.decode() method.

max_num_fields: int. If set, then throws a ValueError if there
    are more than n fields read by parse_qsl().

separator: str. The symbol to use for separating the query arguments.
    Defaults to &.

Returns a dictionary.

## Related

- [parse_qsl](/urllib/parse/parse_qsl.md)
- [quote](/urllib/parse/quote.md)
- [quote_from_bytes](/urllib/parse/quote_from_bytes.md)
