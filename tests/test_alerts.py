import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.alert_noise import reduce_alert_noise

def alert(id='a', time='2026-01-01T10:00:00Z', **kwargs):
    return {'alert_id': id, 'environment': 'production', 'service': 'checkout',
            'alert_name': 'HighErrors', 'severity': 'warning', 'timestamp': time, **kwargs}

class AlertTests(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {'ENVIRONMENT': 'development', 'API_KEY': ''}):
            self.client = TestClient(create_app())

    def test_duplicate_cooldown_boundary(self):
        result=reduce_alert_noise([alert('c','2026-01-01T10:15:00Z'), alert(), alert('b','2026-01-01T10:14:59Z')])
        self.assertEqual([x['alert_id'] for x in result['actionable_alerts']], ['a','c'])
        self.assertEqual(result['summary']['suppressed'], 1)

    def test_environment_and_severity_are_separate(self):
        result=reduce_alert_noise([alert(), alert('b',environment='staging'), alert('c',severity='critical')])
        self.assertEqual(result['summary']['actionable'],3)

    def test_normalization_and_message_changes(self):
        result=reduce_alert_noise([alert(message='counter 1'),alert('b',service=' CHECKOUT ',message='counter 2')])
        self.assertEqual(result['summary']['suppressed'],1)

    def test_low_severity(self):
        result=reduce_alert_noise([alert(severity='info')])
        self.assertEqual(result['summary']['reasons'],{'below_minimum_severity':1})

    def test_zero_cooldown_and_empty_batch(self):
        self.assertEqual(reduce_alert_noise([alert(),alert('b')],0)['summary']['suppressed'],0)
        self.assertEqual(reduce_alert_noise([])['summary']['reduction_percent'],0)

    def test_timezone_equivalence(self):
        result=reduce_alert_noise([alert(),alert('b','2026-01-01T15:30:00+05:30')])
        self.assertEqual(result['summary']['suppressed'],1)

    def test_duplicate_ids_and_naive_timestamps_rejected(self):
        for events in [[alert(),alert()], [alert(time='2026-01-01T10:00:00')]]:
            self.assertEqual(self.client.post('/reduce-alert-noise',json={'alerts':events}).status_code,422)

    def test_excessive_batch_rejected(self):
        self.assertEqual(self.client.post('/reduce-alert-noise',json={'alerts':[alert(str(i)) for i in range(1001)]}).status_code,422)

    def test_body_limit(self):
        response=self.client.post('/reduce-alert-noise',content=b' '*(1048576+1))
        self.assertEqual(response.status_code,413)

    def test_authentication_and_request_id(self):
        with patch.dict(os.environ, {'API_KEY':'x'*32,'ENVIRONMENT':'production'}):
            client=TestClient(create_app())
        self.assertEqual(client.post('/reduce-alert-noise',json={'alerts':[]}).status_code,401)
        response=client.post('/reduce-alert-noise',json={'alerts':[]},headers={'X-API-Key':'x'*32})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.headers['X-Request-ID']),32)
        self.assertEqual(client.get('/health').status_code,200)

    def test_production_requires_key(self):
        with patch.dict(os.environ, {'API_KEY':'','ENVIRONMENT':'production'}):
            with self.assertRaises(RuntimeError): create_app()

    def test_validation_does_not_echo_input(self):
        response=self.client.post('/reduce-alert-noise',json={'alerts':[alert(severity='secret-value')]})
        self.assertEqual(response.status_code,422)
        self.assertNotIn('secret-value',response.text)
