import pathlib

import pytest

from lean_review.workspace import Workspace

HEAD = "a" * 40
BASE = "b" * 40

DIFF = """diff --git a/Lib/Foo.lean b/Lib/Foo.lean
index 1111111..2222222 100644
--- a/Lib/Foo.lean
+++ b/Lib/Foo.lean
@@ -1,3 +1,4 @@
 import Mathlib
+theorem foo : True := trivial
 
 theorem bar : True := trivial
diff --git a/Lib/Gone.lean b/Lib/Gone.lean
deleted file mode 100644
--- a/Lib/Gone.lean
+++ /dev/null
@@ -1 +0,0 @@
-theorem gone : True := trivial
"""


@pytest.fixture
def ws(tmp_path):
    return Workspace(repo="owner/Lib", pr=7, head=HEAD, base=BASE, merge_base=BASE,
                     root=tmp_path, diff_text=DIFF, changed=["Lib/Foo.lean", "Lib/Gone.lean"],
                     title="Add foo", description="body")
