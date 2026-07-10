# lessons.md — airtight-loop

Format: `[date] | what went wrong | rule to prevent it`

[2026-07-08] | Environment had no Java/Maven pre-installed (`/usr/bin/java` was
just the macOS "install Java" stub) | Before running any `mvn`/`java` command in
this repo, confirm the toolchain first (`java -version`, `mvn -version`); if
missing, `brew install openjdk@21 maven` and prepend
`/opt/homebrew/opt/openjdk@21/bin` to PATH — Maven's own `openjdk` dependency is
a different (newer) version and that's fine, `maven.compiler.source/target` in
`engine/pom.xml` pins the language level regardless of which JDK runs the build.

[2026-07-08] | The Odds API's headline "500 free" is credits, not requests —
cost per call is `markets x regions`, so a naive read of the free-tier page would
lead to over-polling and burning the monthly quota in a handful of calls |
Always re-derive real usable call volume from the *cost formula*, not the
headline number, before sizing a poll interval against a paid-tier-adjacent API.

[2026-07-09] | The repo lived at `~/Desktop/Applications/Novig/airtight-loop`,
inside macOS's iCloud "Desktop & Documents" sync (FileProvider-backed). `git
status`/`git log`/`mv` all hung indefinitely (not just slow — one stray `mv` on
this same volume from an unrelated project sat stuck for hours). Root cause was
the FileProvider virtualizing recursive stat/mmap/rename operations, worsened by
the disk being at 98% capacity (5.3GB free) at the same time — two separate
problems that looked like one. Freeing ~12.8GB of regenerable app caches
(`~/Library/Caches/{ms-playwright,Google,go-build,pnpm,*.ShipIt}`, `brew
cleanup`) fixed disk pressure but did NOT fix the git hangs — confirmed by
testing git in a fresh non-iCloud scratch dir (instant) vs. the repo's iCloud
path (still hung after cleanup). | **Never do real engineering work inside
`~/Desktop` or `~/Documents` on a Mac with iCloud Drive sync on** — clone/move
repos to a plain local path (`~/dev/<repo>`) instead. If `git status` ever hangs
(vs. just being slow), suspect FileProvider before assuming disk space or repo
corruption — test by running the same git command in a throwaway dir outside
iCloud sync; if that's instant, it's the sync, not git or the repo. Recover any
gitignored-but-real local artifacts (captured data, `.env`) via individual
Read/Write before abandoning the old path — bulk `cp`/`mv`/`rm -rf` on a
FileProvider path can hang exactly like `git status` did; a fresh `git clone`
from the remote (network read) sidesteps the local bottleneck entirely.

[2026-07-10] | After the move above, I verified the old and new copies
matched by diffing file *listings* (`find` output) only — that catches
missing/extra files but not content drift in files tracked in both places.
A full, real Day-3 Opus-checkpoint verdict (~100 lines) had been written to
the old copy's `tasks/todo.md` by an earlier session but never committed,
so it was silently absent from the fresh `git clone` and Day 4 almost got
built on a repo missing that record. Caught only by noticing a `### Day 3 —
PASS` heading in earlier chat context that didn't match `grep` on the new
clone, then diffing every tracked file's *content* (`git show HEAD:<path>`
vs. the old copy) to confirm it was the only casualty. | When abandoning a
working copy for a fresh clone, diff tracked-file *content* against the old
copy, not just file existence — don't assume a file-listing match means
content match if `git status` was never confirmed clean in the old copy
before switching away from it.
