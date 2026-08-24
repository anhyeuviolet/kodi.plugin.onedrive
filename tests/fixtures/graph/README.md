# Recorded Graph fixtures

Captured from a live OneDrive account, then rewritten.

**Every name, identifier, URL and paging token in these files is synthetic.**
The response *shapes* are real -- the keys, the nesting, the HTTP statuses, the
presence or absence of a facet, the number of entries on a page -- and those are
what the tests read. The values are not, and nothing here can be traced to an
account, a tenant or a file.

Names are replaced by names carrying the same awkward properties as the
originals: a space, a non-ASCII letter, a bracket, an extension. That is
deliberate. A fixture set of tidy ASCII names would pass while the real drive
broke, which is the failure this set exists to prevent.

Written by `scrub_fixtures.py`. The raw captures it reads are never committed.
