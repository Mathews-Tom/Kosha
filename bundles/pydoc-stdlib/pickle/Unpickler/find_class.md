---
type: reference
title: "pickle.Unpickler.find_class"
description: "Return an object from a specified module."
tags: ["pickle", "stdlib"]
---
# pickle.Unpickler.find_class

Return an object from a specified module.

If necessary, the module will be imported. Subclasses may override
this method (e.g. to restrict unpickling of arbitrary classes and
functions).

This method is called whenever a class or a function object is
needed.  Both arguments passed are str objects.

## Related

- [load](/pickle/Unpickler/load.md)
- [decode_long](/pickle/decode_long.md)
- [dump](/pickle/dump.md)
