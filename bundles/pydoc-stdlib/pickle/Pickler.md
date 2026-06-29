---
type: reference
title: "pickle.Pickler"
description: "This takes a binary file for writing a pickle data stream."
tags: ["pickle", "stdlib"]
---
# pickle.Pickler

This takes a binary file for writing a pickle data stream.

The optional *protocol* argument tells the pickler to use the given
protocol; supported protocols are 0, 1, 2, 3, 4 and 5.  The default
protocol is 4. It was introduced in Python 3.4, and is incompatible
with previous versions.

Specifying a negative protocol version selects the highest protocol
version supported.  The higher the protocol used, the more recent the
version of Python needed to read the pickle produced.

The *file* argument must have a write() method that accepts a single
bytes argument. It can thus be a file object opened for binary
writing, an io.BytesIO instance, or any other custom object that meets
this interface.

If *fix_imports* is True and protocol is less than 3, pickle will try
to map the new Python 3 names to the old module names used in Python
2, so that the pickle data stream is readable with Python 2.

If *buffer_callback* is None (the default), buffer views are
serialized into *file* as part of the pickle stream.

If *buffer_callback* is not None, then it can be called any number
of times with a buffer view.  If the callback returns a false value
(such as None), the given buffer is out-of-band; otherwise the
buffer is serialized in-band, i.e. inside the pickle stream.

It is an error if *buffer_callback* is not None and *protocol*
is None or smaller than 5.

## Related

- [clear_memo](/pickle/Pickler/clear_memo.md)
- [Unpickler](/pickle/Unpickler.md)
- [find_class](/pickle/Unpickler/find_class.md)
