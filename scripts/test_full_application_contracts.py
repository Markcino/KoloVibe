"""Phase 2 design contracts: integrity, ownership and compatibility, not runtime acceptance."""
import ast
import copy
import json
from pathlib import Path
import unittest

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'docs/architecture/DOC-205_OpenAPI_3_1_DRAFT.yaml'
CATALOGUE = ROOT / 'packages/contracts/events/catalogue.yaml'
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}


def audit_kinds():
    """Read the actual allowlist without importing Django or executing application code."""
    tree = ast.parse((ROOT / 'services/audit/service/events.py').read_text())
    values = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = {t.id for t in node.targets if isinstance(t, ast.Name)}
        if 'KINDS' in names:
            values['KINDS'] = ast.literal_eval(node.value)
        if 'PRODUCER_KINDS' in names:
            return {ast.literal_eval(k): sorted(values[v.id] if isinstance(v, ast.Name)
                                                else ast.literal_eval(v))
                    for k, v in zip(node.value.keys, node.value.values)}
    raise AssertionError('Audit allowlist not found')


class FullApplicationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = yaml.safe_load(API.read_text())
        cls.catalogue = yaml.safe_load(CATALOGUE.read_text())
        cls.operations = [(p, m, op) for p, item in cls.api['paths'].items()
                          for m, op in item.items() if m in METHODS]

    def test_openapi_is_valid_and_operation_ids_are_unique(self):
        validate(self.api)
        ids = [op['operationId'] for _, _, op in self.operations]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_operation_has_an_approved_service_owner(self):
        owners = {'gateway', 'identity', 'creators', 'content', 'engagement', 'points',
                  'moderation', 'audit', 'business', 'finance', 'events', 'advertising'}
        for path, method, op in self.operations:
            with self.subTest(path=path, method=method):
                self.assertIn(op['x-service-owner'], owners)
                if op.get('x-implementation') == 'planned':
                    self.assertTrue(op['x-requirements'])
                    self.assertTrue(op['x-authorization'])
                    self.assertTrue(op['x-capability'])
                    self.assertIn('Pending', op['x-approval-status'])
                    if method in {'post', 'patch', 'put', 'delete'} and not path.startswith('/webhooks/'):
                        self.assertIn({'$ref': '#/components/parameters/P2Idempotency'}, op['parameters'])

    def test_provider_callbacks_belong_only_to_finance_and_never_bearer_auth(self):
        for path in ['/webhooks/payments/{provider}', '/webhooks/stores/{store}']:
            op = self.api['paths'][path]['post']
            self.assertEqual(op['x-service-owner'], 'finance')
            self.assertEqual(op['security'], [{'providerSignature': []}])
            self.assertEqual(op['x-implementation'], 'planned')
            self.assertIn('BLOCKED', op['description'])

    def test_money_rejects_floats_negative_and_client_authority(self):
        schema = self.api['components']['schemas']['P2Money']
        validator = Draft202012Validator(schema)
        self.assertTrue(validator.is_valid({'amount': '12.34', 'currency': 'USD'}))
        for bad in [12.34, 12, '-1.00', '1e2', 'NaN', '01.20']:
            self.assertFalse(validator.is_valid({'amount': bad, 'currency': 'USD'}), bad)
        self.assertFalse(validator.is_valid({'amount': '1', 'currency': 'usd'}))
        order = Draft202012Validator(self.api['components']['schemas']['P2OrderCreate'], format_checker=FormatChecker())
        valid = {'reservation_id': '123e4567-e89b-42d3-a456-426614174000'}
        self.assertTrue(order.is_valid(valid))
        for field in ['price', 'total', 'owner_id', 'account_id', 'state']:
            self.assertFalse(order.is_valid({**valid, field: 'untrusted'}))

    def test_comments_use_approved_development_limit_and_no_actor_input(self):
        schema = self.api['components']['schemas']['P2CommentWrite']
        v = Draft202012Validator(schema)
        self.assertTrue(v.is_valid({'text': 'A' * 500}))
        self.assertFalse(v.is_valid({'text': 'A' * 501}))
        self.assertFalse(v.is_valid({'text': ''}))
        self.assertFalse(v.is_valid({'text': 'hello', 'author_id': 'spoofed'}))

    def test_builtin_event_catalogue_covers_privacy_and_qualified_view(self):
        actual = {(e['event_type'], e['producer'], e['consumer'])
                  for e in self.catalogue['events'] if e['status'] == 'built'}
        expected = {('dec003.qualified_view', 'engagement', 'points')}
        for service in ['engagement', 'creators', 'content', 'moderation', 'business']:
            expected.update((kind, 'identity', service) for kind in
                            ['privacy.erasure_requested', 'privacy.export_requested'])
            expected.update((kind, service, 'identity') for kind in
                            ['privacy.erasure_confirmed', 'privacy.export_delivered'])
        self.assertEqual(actual, expected)
        for event in self.catalogue['events']:
            self.assertIn(event['schema'], self.catalogue['schemas'])
            self.assertEqual(event['exchange'], event['routing_key'])
            self.assertEqual(event['queue'], event['exchange'])
        content = [e for e in self.catalogue['events']
                   if e['status'] == 'built' and e['consumer'] == 'content']
        self.assertTrue(all(e['queue'] == 'kolovibe.content.media' for e in content))

    def test_catalogued_audit_http_kinds_match_actual_allowlist(self):
        self.assertEqual(self.catalogue['audit_http']['producers'], audit_kinds())
        self.assertIn('not RabbitMQ', self.catalogue['audit_http']['transport'])

    def test_all_event_schemas_are_valid_and_strict_at_the_envelope(self):
        for name, schema in self.catalogue['schemas'].items():
            with self.subTest(name=name):
                Draft202012Validator.check_schema(schema)
                self.assertFalse(schema['additionalProperties'])
        keys = [(e['event_type'], e['producer'], e['consumer']) for e in self.catalogue['events']]
        self.assertEqual(len(keys), len(set(keys)))

    def test_domain_signature_cannot_be_replaced_by_payload_identity(self):
        for e in self.catalogue['events']:
            if e['status'] != 'planned':
                continue
            schema = self.catalogue['schemas'][e['schema']]
            self.assertEqual(schema['properties']['producer'], {'const': e['producer']})
            self.assertEqual(schema['properties']['type'], {'const': e['event_type']})
            self.assertIn('envelope signature', e['authorization'])
            self.assertIn('payload_hash', schema['required'])

    def test_financial_success_schema_rejects_wrong_producer_currency_and_float(self):
        schema = self.catalogue['schemas']['kolovibe_finance_payment_succeeded_v1']
        event = {'schema_version': 1, 'event_id': '123e4567-e89b-42d3-a456-426614174000',
                 'producer': 'finance', 'type': 'kolovibe.finance.payment.succeeded.v1',
                 'occurred_at': '2026-11-27T15:00:00Z', 'aggregate_id': '123e4567-e89b-42d3-a456-426614174000',
                 'aggregate_version': 1, 'correlation_id': '123e4567-e89b-42d3-a456-426614174000',
                 'payload_hash': 'a' * 64,
                 'data': {'order_id': '123e4567-e89b-42d3-a456-426614174000',
                          'payment_id': '123e4567-e89b-42d3-a456-426614174000',
                          'journal_id': '123e4567-e89b-42d3-a456-426614174000',
                          'money': {'amount': '10.00', 'currency': 'USD'}}}
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertTrue(validator.is_valid(event))
        for key, val in [('producer', 'points'), ('schema_version', 2), ('payload_hash', 'bad')]:
            changed = copy.deepcopy(event)
            changed[key] = val
            self.assertFalse(validator.is_valid(changed))
        changed = copy.deepcopy(event)
        changed['data']['money']['amount'] = 10.00
        self.assertFalse(validator.is_valid(changed))
        changed = copy.deepcopy(event)
        changed['data']['comment_text'] = 'personal text'
        self.assertFalse(validator.is_valid(changed))

    def test_points_only_supplies_a_weight_snapshot_to_finance(self):
        points = [e for e in self.catalogue['events'] if e['producer'] == 'points']
        self.assertEqual({e['event_type'] for e in points}, {'kolovibe.points.eligible_snapshot.finalized.v1'})
        self.assertTrue(all(e['consumer'] == 'finance' for e in points))
        data = self.catalogue['schemas'][points[0]['schema']]['properties']['data']
        self.assertNotIn('money', data['properties'])
        self.assertIn('snapshot_hash', data['properties'])

class ApprovedRequirementTraceabilityTests(unittest.TestCase):
    def test_each_actual_row_of_the_five_approved_sets_is_in_the_canonical_matrix(self):
        import csv
        import re
        with (ROOT / 'docs/governance/phase1/PHASE-01_Feature_Traceability_Matrix.csv').open() as source:
            matrix = list(csv.DictReader(source))
        mapped = set(re.findall(r'(?:NT|PAY|GA|DST|CM)-R-\d{3}',
                                ' '.join(r['Detailed approved requirements'] for r in matrix)))
        source_ids = set()
        for area in ['NT', 'PAY', 'GA', 'DST', 'CM']:
            source = next((ROOT / 'docs/requirements').glob(f'FP-{area}_*'))
            self.assertIn('Status: APPROVED by the owner', source.read_text())
            source_ids.update(re.findall(r'^\| (' + area + r'-R-\d{3}) \|', source.read_text(), re.M))
        self.assertEqual(mapped, source_ids)
        self.assertTrue(all(r['GitHub issue'] for r in matrix
                            if r['Current implementation status'] != 'Explicitly excluded'))


if __name__ == '__main__':
    unittest.main()
