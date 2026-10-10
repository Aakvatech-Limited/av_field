"""Sync transaction tests with a fake Frappe boundary; real-site checks are separate."""
import importlib
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch
from av_field.validation import fingerprint, normalize, operation_name

# Isolate the framework boundary; run the actual push implementation.
fake = types.ModuleType('frappe')
fake.whitelist = lambda **kwargs: lambda fn: fn
fake.parse_json = lambda value: json.loads(value) if isinstance(value, str) else value
fake.session = types.SimpleNamespace(user='agent@example.com')
fake.PermissionError = PermissionError
fake.DuplicateEntryError = type('DuplicateEntryError', (Exception,), {})
fake.has_permission = Mock(return_value=True)
fake.db = Mock()
fake.get_doc = Mock()
def throw(message, error=ValueError): raise error(message)
fake.throw = throw
utils = types.ModuleType('frappe.utils'); utils.getdate = Mock(); utils.nowdate = Mock()
records = types.ModuleType('av_field.records'); records.require_agent = Mock(); records.check_master = Mock(); records.conversion_guard = Mock()
with patch.dict(sys.modules, {'frappe': fake, 'frappe.utils': utils, 'av_field.records': records}):
    api = importlib.import_module('av_field.api')


def operation():
    return {'version':1, 'id':'323da969-8049-4119-9235-a7e8f0b0e380', 'kind':'visit',
            'recorded_at':'2026-10-10T11:00:00Z', 'payload':{'customer':'C1','notes':'Visit'}}


class PushTests(unittest.TestCase):
    def setUp(self):
        fake.db.reset_mock(); fake.get_doc.reset_mock(); records.require_agent.reset_mock();
        fake.db.exists.side_effect = None; fake.db.exists.return_value = False
        fake.session.user = 'agent@example.com'
        self.op = operation()
        self.doc = types.SimpleNamespace(submitted_by=fake.session.user,
            payload_hash=fingerprint(normalize(self.op)), check_permission=Mock(), insert=Mock())
        fake.get_doc.side_effect = None; fake.get_doc.return_value = self.doc

    def test_new_push_inserts_once_and_does_not_commit_early(self):
        ack = api.push(self.op, expected_user=fake.session.user)
        self.assertFalse(ack['duplicate']); self.doc.insert.assert_called_once()
        fake.db.commit.assert_not_called()
        self.assertEqual(ack['name'], operation_name(fake.session.user,self.op['id']))

    def test_replay_after_lost_response_returns_existing_ack(self):
        fake.db.exists.return_value = True
        ack = api.push(self.op, expected_user=fake.session.user)
        self.assertTrue(ack['duplicate']); self.doc.insert.assert_not_called()
        self.doc.check_permission.assert_called_with('read')

    def test_reused_uuid_with_modified_data_is_rejected(self):
        fake.db.exists.return_value = True; self.op['payload']['notes'] = 'Different'
        with self.assertRaisesRegex(ValueError,'different data'): api.push(self.op, expected_user=fake.session.user)
        self.doc.insert.assert_not_called()

    def test_concurrent_duplicate_rolls_back_savepoint_then_acknowledges(self):
        self.doc.insert.side_effect = fake.DuplicateEntryError()
        ack = api.push(self.op, expected_user=fake.session.user)
        fake.db.rollback.assert_called_once_with(save_point='field_push')
        self.assertTrue(ack['duplicate'])

    def test_ack_cannot_belong_to_other_account(self):
        fake.db.exists.return_value = True; self.doc.submitted_by = 'someone@example.com'
        with self.assertRaises(ValueError): api.push(self.op, expected_user=fake.session.user)

    def test_account_change_between_context_and_upload_is_rejected(self):
        with self.assertRaises(PermissionError):
            api.push(self.op, expected_user="previous@example.com")
        self.doc.insert.assert_not_called()

    def test_create_permission_is_required_before_insert(self):
        fake.has_permission.reset_mock()
        api.push(self.op, expected_user=fake.session.user)
        fake.has_permission.assert_called_once_with('Field Visit','create',throw=True)

if __name__ == '__main__': unittest.main()
