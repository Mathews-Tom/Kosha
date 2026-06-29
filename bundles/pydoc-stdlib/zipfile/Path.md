---
type: reference
title: "zipfile.Path"
description: "A :class:`importlib.resources.abc.Traversable` interface for zip files."
tags: ["zipfile", "stdlib"]
---
# zipfile.Path

A :class:`importlib.resources.abc.Traversable` interface for zip files.

Implements many of the features users enjoy from
:class:`pathlib.Path`.

Consider a zip file with this structure::

    .
    ├── a.txt
    └── b
        ├── c.txt
        └── d
            └── e.txt

>>> data = io.BytesIO()
>>> zf = ZipFile(data, 'w')
>>> zf.writestr('a.txt', 'content of a')
>>> zf.writestr('b/c.txt', 'content of c')
>>> zf.writestr('b/d/e.txt', 'content of e')
>>> zf.filename = 'mem/abcde.zip'

Path accepts the zipfile object itself or a filename

>>> root = Path(zf)

From there, several path operations are available.

Directory iteration (including the zip file itself):

>>> a, b = root.iterdir()
>>> a
Path('mem/abcde.zip', 'a.txt')
>>> b
Path('mem/abcde.zip', 'b/')

name property:

>>> b.name
'b'

join with divide operator:

>>> c = b / 'c.txt'
>>> c
Path('mem/abcde.zip', 'b/c.txt')
>>> c.name
'c.txt'

Read text:

>>> c.read_text(encoding='utf-8')
'content of c'

existence:

>>> c.exists()
True
>>> (b / 'missing.txt').exists()
False

Coercion to string:

>>> import os
>>> str(c).replace(os.sep, posixpath.sep)
'mem/abcde.zip/b/c.txt'

At the root, ``name``, ``filename``, and ``parent``
resolve to the zipfile. Note these attributes are not
valid and will raise a ``ValueError`` if the zipfile
has no filename.

>>> root.name
'abcde.zip'
>>> str(root.filename).replace(os.sep, posixpath.sep)
'mem/abcde.zip'
>>> str(root.parent)
'mem'

## Related

- [open](/zipfile/Path/open.md)
- [ZipFile](/zipfile/ZipFile.md)
- [extract](/zipfile/ZipFile/extract.md)
