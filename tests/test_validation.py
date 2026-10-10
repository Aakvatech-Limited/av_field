import copy
import unittest
from av_field.validation import InvalidOperation, fingerprint, normalize, operation_name


def operation(kind='visit'):
    payload = {'customer': 'CUST-001', 'notes': 'Met the store manager'}
    if kind == 'order':
        payload['items'] = [{'item_code': 'ITEM-001', 'qty': 2}]
    return {'version': 1, 'id': '323da969-8049-4119-9235-a7e8f0b0e380',
            'kind': kind, 'recorded_at': '2026-10-10T14:00:00+03:00', 'payload': payload}


class ContractTests(unittest.TestCase):
    def test_same_operation_has_stable_fingerprint(self):
        clean = normalize(operation())
        self.assertEqual(clean['recorded_at'], '2026-10-10T11:00:00+00:00')
        self.assertEqual(fingerprint(clean), fingerprint(normalize(copy.deepcopy(clean))))

    def test_accounts_cannot_share_operation_names(self):
        self.assertNotEqual(operation_name('agent1', operation()['id']), operation_name('agent2', operation()['id']))

    def test_zero_coordinates_are_valid(self):
        op = operation(); op['payload'].update(latitude=0, longitude=0)
        self.assertEqual(normalize(op)['payload']['latitude'], 0)
        self.assertEqual(normalize(op)['payload']['accuracy'], 0)

    def test_decimal_precision_matches_database_fields(self):
        op = operation(); op['payload'].update(latitude=-6.123456789, longitude=39.123456789, accuracy=12.3456)
        clean = normalize(op)
        self.assertEqual(clean['payload']['accuracy'], 12.35)
        self.assertEqual(fingerprint(clean), fingerprint(normalize(clean)))

    def test_rejects_incomplete_location(self):
        op = operation(); op['payload']['latitude'] = 1
        with self.assertRaises(InvalidOperation): normalize(op)

    def test_rejects_rates_owner_and_server_fields(self):
        for key in ('rate', 'owner', 'submitted_by', 'sales_order'):
            op = operation(); op['payload'][key] = 'injected'
            with self.assertRaises(InvalidOperation): normalize(op)

    def test_rejects_invalid_quantities(self):
        for qty in (0, -1, True, '2', float('inf'), float('nan'), 1000001):
            op = operation('order'); op['payload']['items'][0]['qty'] = qty
            with self.assertRaises(InvalidOperation): normalize(op)

    def test_rejects_duplicate_items(self):
        op = operation('order'); op['payload']['items'] *= 2
        with self.assertRaises(InvalidOperation): normalize(op)

    def test_rejects_empty_and_oversized_orders(self):
        for items in ([], [{'item_code': str(i), 'qty': 1} for i in range(101)]):
            op = operation('order'); op['payload']['items'] = items
            with self.assertRaises(InvalidOperation): normalize(op)

    def test_rejects_invalid_metadata(self):
        for key, value in [('version', 2), ('version', True), ('id', 'wrong'), ('recorded_at', '2026-10-10'), ('kind', 'invoice')]:
            op = operation(); op[key] = value
            with self.assertRaises(InvalidOperation): normalize(op)
        for op in (None, [], 'text'):
            with self.assertRaises(InvalidOperation): normalize(op)

    def test_changed_payload_has_different_fingerprint(self):
        op = operation(); other = copy.deepcopy(op); other['payload']['notes'] = 'changed'
        self.assertNotEqual(fingerprint(normalize(op)), fingerprint(normalize(other)))

if __name__ == '__main__': unittest.main()
