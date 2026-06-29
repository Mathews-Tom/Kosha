---
type: reference
title: "pickle.Pickler.clear_memo"
description: "Clears the pickler's \"memo\"."
tags: ["pickle", "stdlib"]
---
# pickle.Pickler.clear_memo

Clears the pickler's "memo".

The memo is the data structure that remembers which objects the
pickler has already seen, so that shared or recursive objects are
pickled by reference and not by value.  This method is useful when
re-using picklers.

## Related

- [Unpickler](/pickle/Unpickler.md)
- [find_class](/pickle/Unpickler/find_class.md)
- [load](/pickle/Unpickler/load.md)
