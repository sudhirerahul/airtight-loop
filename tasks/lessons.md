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
