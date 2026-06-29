---
type: reference
title: "pickle.islice"
description: "islice(iterable, stop) --> islice object"
tags: ["pickle", "stdlib"]
---
# pickle.islice

islice(iterable, stop) --> islice object
islice(iterable, start, stop[, step]) --> islice object

Return an iterator whose next() method returns selected values from an
iterable.  If start is specified, will skip all preceding elements;
otherwise, start defaults to zero.  Step defaults to one.  If
specified as another value, step determines how many values are
skipped between successive calls.  Works like a slice() on a list
but returns an iterator.

## Related

- [load](/pickle/load.md)
- [loads](/pickle/loads.md)
- [pack](/pickle/pack.md)
