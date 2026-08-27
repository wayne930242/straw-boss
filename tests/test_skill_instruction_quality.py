from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalized(path: Path) -> str:
    return " ".join(path.read_text().replace("`", "").split())


class SkillInstructionQualityTests(unittest.TestCase):
    def test_skills_have_no_defensive_red_flags_sections(self) -> None:
        offenders = [
            path.relative_to(ROOT).as_posix()
            for path in sorted((ROOT / "skills").glob("*/SKILL.md"))
            if "## Red Flags" in path.read_text()
        ]
        self.assertEqual(offenders, [])

    def test_skills_have_no_quoted_hypothetical_defense_bullets(self) -> None:
        offenders: list[str] = []
        pattern = re.compile(r'^\s*-\s+["“][^"”]+["”]\s*[—-]', re.MULTILINE)
        for path in sorted((ROOT / "skills").glob("**/*.md")):
            if pattern.search(path.read_text()):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_init_delegates_app_owned_reconnaissance(self) -> None:
        source = normalized(ROOT / "skills" / "init" / "SKILL.md")
        self.assertIn(
            "dispatch bounded reconnaissance rooted in each confirmed app",
            source,
        )
        self.assertIn("returns proposed fields with evidence references", source)
        self.assertNotIn("read each app's git log", source)
        self.assertNotIn("grep every app's skills", source)

    def test_harness_has_no_guessed_default_artifacts(self) -> None:
        source = normalized(ROOT / "skills" / "create-great-harness" / "SKILL.md")
        self.assertIn("CLAUDE.md is the only unconditional artifact", source)
        self.assertIn("concrete project evidence or explicit confirmed scope", source)
        self.assertNotIn("universally applicable", source)
        self.assertNotIn("single most common irreversible-mistake footgun", source)
        self.assertNotIn("Target under 100 lines", source)
        self.assertNotIn("Every app this bootstraps starts with zero skills", source)

    def test_moving_base_refresh_is_conditional(self) -> None:
        source = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "plan-mechanics.md"
        )
        self.assertIn(
            "When parallel tasks target the same moving base or the remote base advanced",
            source,
        )
        self.assertNotIn("Every full-flow dispatch instruction in a plan/batch MUST", source)

    def test_batch_and_single_app_routing_have_bounded_scope(self) -> None:
        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        work_on = normalized(ROOT / "skills" / "work-on" / "SKILL.md")
        self.assertIn("A batch may contain independent items", dispatching)
        self.assertNotIn("batch is one multi-app unit of work only", dispatching)
        self.assertIn("unless the request is explicitly outside that app", work_on)
        self.assertNotIn("every request resolves to it", work_on)

    def test_investigation_contract_is_positive_and_consistent(self) -> None:
        for skill_name in (
            "inspecting-app",
            "investigating-app",
            "troubleshooting-app",
        ):
            source = normalized(ROOT / "skills" / skill_name / "SKILL.md")
            self.assertIn("evidence references", source)
            self.assertNotIn("not a yes-or-no answer", source)
        troubleshooting = normalized(
            ROOT / "skills" / "troubleshooting-app" / "SKILL.md"
        )
        self.assertNotIn("from your own diagnosis", troubleshooting)
        lifecycle_tests = (
            ROOT / "tests" / "test_dispatched_agent_lifecycle_transport.py"
        ).read_text()
        self.assertNotIn("Do not investigate the target app to enrich the brief", lifecycle_tests)
        self.assertNotIn('self.assertIn("not a yes-or-no answer"', lifecycle_tests)

    def test_troubleshooting_splits_only_integration_preflight(self) -> None:
        source = normalized(ROOT / "skills" / "troubleshooting-app" / "SKILL.md")
        self.assertIn("only when both conditions hold", source)
        self.assertIn("failure crosses an integration boundary", source)
        self.assertIn("needed to shape or schedule later dispatches", source)
        self.assertIn("stays in the same worker", source)
        self.assertIn("every other app-level or uncertain failure", source)
        self.assertIn("One worker reproduces the failure", source)

    def test_shared_resource_discovery_stays_with_worker(self) -> None:
        source = normalized(
            ROOT
            / "skills"
            / "dispatching-work"
            / "references"
            / "shared-resource-coordination.md"
        )
        self.assertIn("worker resolves the target app's actual resource configuration", source)
        self.assertIn("Only a resource shared across concurrent tasks is locked", source)
        self.assertNotIn("Every port a worktree's dev server actually binds to gets locked", source)
        self.assertNotIn("defaults are not safe to leave unexamined", source)

    def test_peek_mechanics_follow_current_artifact_schema(self) -> None:
        source = normalized(
            ROOT / "skills" / "peeking-work" / "references" / "peek-mechanics.md"
        )
        self.assertIn("instruction records mode, session_id, and repo_root", source)
        self.assertIn("launch receipt records the agent name and pane", source)
        self.assertIn(
            "status record supplies progress state, note, optional evidence references",
            source,
        )
        self.assertIn("rather than routing data", source)
        self.assertNotIn("dispatch/<session_id>.json", source)

    def test_coordination_lifecycle_is_event_driven(self) -> None:
        orchestrator = normalized(ROOT / "skills" / "i-am-orchestrator" / "SKILL.md")
        self.assertIn("Keep the lifecycle event-driven", orchestrator)
        self.assertIn("A dispatch reports itself", orchestrator)
        self.assertIn(
            "spend the time between events on other coordination or on the user's conversation",
            orchestrator,
        )
        self.assertIn(
            "when observed evidence and its recorded state actually disagree, or when the user asks",
            orchestrator,
        )
        self.assertNotIn("watch status", orchestrator)
        self.assertNotIn("every dispatch is observed or terminal", orchestrator)

        roles = normalized(ROOT / "docs" / "roles.md")
        self.assertIn("status-event handling", roles)
        self.assertIn(
            "That persisted status and its notification are what drive the coordination lifecycle",
            roles,
        )
        self.assertNotIn("status observation", roles)
        self.assertNotIn("observe status", roles)

        dispatching = normalized(ROOT / "skills" / "dispatching-work" / "SKILL.md")
        self.assertIn(
            "Report, then run the lifecycle on the dispatch's own events", dispatching
        )
        self.assertIn(
            "Between events the task is running and the main agent is free for other coordination",
            dispatching,
        )

        shipping = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("the answer arrives as its next status event", shipping)
        self.assertNotIn("pane/process observation", shipping)

        for reference in ("cross-session-coordination.md", "dispatch-mechanics.md"):
            source = normalized(
                ROOT / "skills" / "dispatching-work" / "references" / reference
            )
            self.assertNotIn("process/watcher observation", source)

    def test_session_start_stance_states_each_coordination_rule_once(self) -> None:
        # The SessionStart hook injects the body only, so judge the body only.
        source = (ROOT / "skills" / "i-am-orchestrator" / "SKILL.md").read_text()
        _, _, body_source = source.partition("---\n")
        _, _, body_source = body_source.partition("---\n")
        stance = " ".join(body_source.replace("`", "").split())

        # Each rule is stated where it is operable, and nowhere else. The
        # injected stance previously restated work-content ownership, conflict
        # handling, and cleanup authority across four sections.
        for phrase in (
            "specification, design, implementation, and verification method",
            "awaiting-main-agent",
            "conflict",
            "authorization",
            "peeking-work",
        ):
            self.assertEqual(stance.count(phrase), 1, phrase)

        # Worker-side mechanism a main agent never executes.
        self.assertNotIn("persists the state first and then notifies", stance)

        # Positive, direct phrasing outside the one negation the section title
        # carries by name.
        body = stance.replace("Own the loop, not the work", "")
        for defensive in (" do not ", " never ", " without asking ", ", not "):
            self.assertNotIn(defensive, body)

    def test_shipping_sync_is_conditional_and_scope_is_local(self) -> None:
        source = normalized(ROOT / "skills" / "shipping-task" / "SKILL.md")
        self.assertIn("If the primary checkout tracks the merged base", source)
        self.assertNotIn("once the worktree is removed, sync the app's primary checkout too", source)
        self.assertNotIn("This finding needs DB/infra access I don't have", source)


if __name__ == "__main__":
    unittest.main()
