"""The Pi skill set keeps the shared workflow and leaves the other hosts' skills alone."""

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PI = ROOT / "pi/skills"
SHARED = ROOT / "skills"
NAMES = ("boss-say", "work-on", "choosing-graph", "shipping-task", "reporting-to-user", "dispatching-work")
OTHER_HOST_MECHANICS = re.compile(
    r"CLAUDE_PLUGIN_ROOT|scripts/|plan\.json|\.straw-boss/plans|\.straw-boss/dispatch|awaiting-(?:main-agent|user-input|authorization)"
    r"|notifying-main-agent|peeking-work|contacting-orchestrators|bringing-coworker|claim-resource|/loop|ScheduleWakeup"
)
PI_MECHANICS = re.compile(r"Pi host|pi-herdr-agents|caller_ping|dispatch_control|subagent_resume")


def pi_skill_files() -> list[Path]:
    return sorted(PI.rglob("*.md"))


def bullets(path: Path, heading: str) -> list[str]:
    section = path.read_text().partition(f"## {heading}")[2].split("\n## ")[0]
    return re.findall(r"^- \*\*([^*]+)\*\*", section, re.M)


class PiSkillSetTests(unittest.TestCase):
    def test_the_pi_set_has_the_six_workflow_skills(self) -> None:
        self.assertEqual({path.parent.name for path in PI.glob("*/SKILL.md")}, set(NAMES))
        for name in NAMES:
            with self.subTest(skill=name):
                self.assertRegex((PI / name / "SKILL.md").read_text(), rf"^---\nname: {name}\ndescription: .+\n---")

    def test_the_pi_set_names_no_other_host_mechanics(self) -> None:
        offenders = [
            f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
            for path in pi_skill_files()
            for number, line in enumerate(path.read_text().splitlines(), 1)
            if OTHER_HOST_MECHANICS.search(line)
        ]
        self.assertEqual(offenders, [])

    def test_the_other_hosts_skills_carry_no_pi_mechanics(self) -> None:
        offenders = [
            str(path.relative_to(ROOT))
            for path in sorted(SHARED.rglob("*.md"))
            if PI_MECHANICS.search(path.read_text())
        ]
        self.assertEqual(offenders, [])

    def test_the_other_hosts_skills_are_unchanged_from_the_last_commit(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--", "skills"], cwd=ROOT, capture_output=True
        )
        if result.returncode not in (0, 1):
            self.skipTest("git is unavailable")
        self.assertEqual(result.returncode, 0, "skills/ differs from HEAD; Pi changes belong in pi/skills/")

    def test_pi_links_resolve_files_and_named_sections(self) -> None:
        for path in pi_skill_files():
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text()):
                if "://" in target:
                    continue
                file, _, anchor = target.partition("#")
                dest = (path.parent / file).resolve() if file else path
                with self.subTest(source=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue(dest.is_file(), target)
                    if anchor:
                        headings = re.findall(r"^#{1,6} (.+)$", dest.read_text(), re.M)
                        slugs = {re.sub(r"[^\w -]", "", h.lower()).replace(" ", "-") for h in headings}
                        self.assertIn(anchor, slugs)

    def test_pi_links_stay_inside_the_pi_set_except_host_neutral_references(self) -> None:
        allowed = {SHARED / "init/references/apps-config-schema.md"}
        for path in pi_skill_files():
            for target in re.findall(r"\[[^\]]+\]\(([^)#]+)", path.read_text()):
                dest = (path.parent / target).resolve()
                with self.subTest(source=str(path.relative_to(ROOT)), target=target):
                    self.assertTrue(dest.is_relative_to(PI) or dest in allowed, target)

    def test_the_pi_set_is_written_in_english(self) -> None:
        offenders = [
            f"{path.relative_to(ROOT)}:{number}"
            for path in pi_skill_files()
            for number, line in enumerate(path.read_text().splitlines(), 1)
            if any("\u4e00" <= character <= "\u9fff" for character in line)
        ]
        self.assertEqual(offenders, [])

    def test_reporting_to_user_is_identical_in_both_sets(self) -> None:
        self.assertEqual(
            (PI / "reporting-to-user/SKILL.md").read_text(),
            (SHARED / "reporting-to-user/SKILL.md").read_text(),
        )

    def test_shared_policy_terms_match_between_the_sets(self) -> None:
        for heading in ("Coordination graphs", "Reality anchors"):
            with self.subTest(section=heading):
                self.assertEqual(
                    bullets(PI / "choosing-graph/SKILL.md", heading),
                    bullets(SHARED / "choosing-graph/SKILL.md", heading),
                )
        for phrase in ("solo-mode", "team-mode", "forbidDirectCommit: true", "gitWorkflowSkill",
                       "Merge and pushes to another tracked branch require user authorization"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, (PI / "shipping-task/SKILL.md").read_text())
                self.assertIn(phrase, (SHARED / "shipping-task/SKILL.md").read_text())
        for name in ("work-on", "boss-say"):
            shared = (SHARED / name / "SKILL.md").read_text()
            pi = (PI / name / "SKILL.md").read_text()
            with self.subTest(skill=name):
                self.assertEqual(shared.split("\n---\n", 1)[0], pi.split("\n---\n", 1)[0])


if __name__ == "__main__":
    unittest.main()
