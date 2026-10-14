import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from skills.catalog import SKILLS, SkillTool, builtin_skill_tools, validate_parameters
from tools.registry import ToolRegistry


class SkillCatalogTests(unittest.TestCase):
    def test_builtin_catalog_has_only_the_five_requested_skills(self):
        self.assertEqual(
            {skill.id for skill in SKILLS},
            {
                "concept-explainer",
                "argument-analyzer",
                "character-tracker",
                "quote-collector",
                "reading-guide",
            },
        )

    def test_skill_tools_are_discoverable_and_have_unique_names(self):
        tools = builtin_skill_tools()
        registry = ToolRegistry(tools)
        schemas = registry.schemas()
        names = [schema["function"]["name"] for schema in schemas]

        self.assertEqual(len(names), 5)
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("skill_concept_explainer", names)
        self.assertNotIn("skill_summarizer", names)

    def test_skill_activation_returns_prompt_and_normalized_arguments(self):
        skill = next(skill for skill in SKILLS if skill.id == "quote-collector")
        result = SkillTool(skill).run(quote_type="insightful", max_quotes=4)

        self.assertEqual(result["__skill__"]["id"], "quote-collector")
        self.assertEqual(result["__skill__"]["arguments"]["max_quotes"], 4)
        self.assertTrue(result["__skill__"]["prompt"])

    def test_skill_parameters_reject_unknown_values_and_out_of_range_limits(self):
        skill = next(skill for skill in SKILLS if skill.id == "quote-collector")

        with self.assertRaisesRegex(ValueError, "unexpected parameter"):
            validate_parameters(skill, {"made_up": True})
        with self.assertRaisesRegex(ValueError, "between 1 and 20"):
            validate_parameters(skill, {"max_quotes": 21})

    def test_skill_parameters_apply_declared_defaults(self):
        skill = next(skill for skill in SKILLS if skill.id == "reading-guide")

        self.assertEqual(validate_parameters(skill, {})["mode"], "discuss")


if __name__ == "__main__":
    unittest.main()
