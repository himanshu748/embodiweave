import copy
import json
from pathlib import Path
import unittest
from ew.rationale import decision_display


class DecisionDisplayTests(unittest.TestCase):
    def test_v4_rejection_is_display_only(self):
        path = Path(__file__).parents[1] / 'evidence/mcp-agent-v4/decision.json'
        before = path.read_bytes()
        record = json.loads(before)
        original = copy.deepcopy(record)
        shown = decision_display(record)
        self.assertIn('safest', record['explanation'])
        self.assertNotIn('safest', shown['explanation'])
        self.assertIn('unsupported comparison', shown['rationale_check']['note'])
        self.assertIn(record['selected'], shown['explanation'])
        self.assertEqual(record, original)
        self.assertEqual(path.read_bytes(), before)
        for key in ('ranking', 'queries', 'mcp_tool_calls'):
            self.assertEqual(shown[key], record[key])

    def test_deterministic_explanation_is_preserved(self):
        record = {'mode': 'deterministic', 'explanation': 'Authored ranking rule.'}
        self.assertEqual(decision_display(record), record)
