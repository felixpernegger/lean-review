### Compatibility policy

Tau Ceti deliberately provides no backwards-compatibility layer. When an API or module is moved,
renamed, replaced, or deleted, all in-repository uses move to the canonical replacement and the
old surface disappears in the same PR. Never request a compatibility alias, wrapper declaration,
forwarding import module, deprecated shim (including `deprecated_module`), or duplicate theorem
name, and require the deletion of any such artifact a PR adds. The source compatibility of external
users pinned to an older revision is not a review requirement and does not qualify as a
user-visible risk here.
