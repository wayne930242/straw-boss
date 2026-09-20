# Vendored fast-jev-compaction

Source: https://github.com/tamaratran/fast-jev-compaction

Commit: `e3f262a7f4d42bd8dd32ced30d26176f7cb545b0`

License: MIT; see [LICENSE](LICENSE).

The source library and tests are vendored. Straw Boss owns the opt-in Claude
adapter, backend measurement, benchmark recovery storage, and renewal integration.
Local library changes accept shared retention criteria and governing-source locks,
preserve whitespace text, wait for every Jev batch to settle, validate score ranges,
and use the recovery archive in truncation notes. The Straw Boss message adapter
uses fresh message identities to fix upstream handle reuse restoring dropped
ancestors on Claude Code 2.1.278 resume.
The upstream plugin is not installed.
