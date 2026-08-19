# Centralize cast, naming, and authority in `docs/roles.md`

No skill file ever defined who the actors are (user / main agent / dispatched agent / subagent), how they're named, or who decides what — `1c71541` had to reactively rename "boss" prose across ~10 files because it ambiguously meant both "user" and "main agent," and `notifying-boss` survives as the same bug at the identifier level. Rather than keep patching this gap with more Red Flags per skill (negation-based, scattered, unverifiable at a glance), we're writing one file — `docs/roles.md` — as the single source of truth, with every `SKILL.md` carrying a short context pointer to it plus the leading words themselves in its own prose. Existing Red Flags get a mechanical pass: fold into `docs/roles.md` as a positive rule if the content can be phrased positively there, otherwise keep as a hard guardrail paired with the positive target it defends.

## Status

Accepted

## Consequences

`docs/architecture.md` stays as-is for design rationale ("why dispatch"); `docs/roles.md` is new and is the one execution-time-relevant doc, unlike `architecture.md` which is explicitly "read this if you're extending the plugin."
