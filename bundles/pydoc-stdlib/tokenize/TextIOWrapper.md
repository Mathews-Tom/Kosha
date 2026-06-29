---
type: reference
title: "tokenize.TextIOWrapper"
description: "Character and line based layer over a BufferedIOBase object, buffer."
tags: ["tokenize", "stdlib"]
---
# tokenize.TextIOWrapper

Character and line based layer over a BufferedIOBase object, buffer.

encoding gives the name of the encoding that the stream will be
decoded or encoded with. It defaults to locale.getencoding().

errors determines the strictness of encoding and decoding (see
help(codecs.Codec) or the documentation for codecs.register) and
defaults to "strict".

newline controls how line endings are handled. It can be None, '',
'\n', '\r', and '\r\n'.  It works as follows:

* On input, if newline is None, universal newlines mode is
  enabled. Lines in the input can end in '\n', '\r', or '\r\n', and
  these are translated into '\n' before being returned to the
  caller. If it is '', universal newline mode is enabled, but line
  endings are returned to the caller untranslated. If it has any of
  the other legal values, input lines are only terminated by the given
  string, and the line ending is returned to the caller untranslated.

* On output, if newline is None, any '\n' characters written are
  translated to the system default line separator, os.linesep. If
  newline is '' or '\n', no translation takes place. If newline is any
  of the other legal values, any '\n' characters written are translated
  to the given string.

If line_buffering is True, a call to flush is implied when a call to
write contains a newline character.

## Related

- [close](/tokenize/TextIOWrapper/close.md)
- [detach](/tokenize/TextIOWrapper/detach.md)
- [fileno](/tokenize/TextIOWrapper/fileno.md)
