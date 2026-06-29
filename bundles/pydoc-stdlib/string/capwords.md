---
type: reference
title: "string.capwords"
description: "capwords(s [,sep]) -> string"
tags: ["string", "stdlib"]
---
# string.capwords

capwords(s [,sep]) -> string

Split the argument into words using split, capitalize each
word using capitalize, and join the capitalized words using
join.  If the optional second argument sep is absent or None,
runs of whitespace characters are replaced by a single space
and leading and trailing whitespace are removed, otherwise
sep is used to split and join the words.
