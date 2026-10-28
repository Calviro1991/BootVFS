import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from bootvfs import classify, load_config, notify, send_whatsapp


class AvailabilityTests(unittest.TestCase):
    def test_failed_email_does_not_block_whatsapp_or_terminal(self):
        with patch('bootvfs.send_email', side_effect=OSError), patch('bootvfs.send_whatsapp') as whatsapp, patch('builtins.print') as output:
            self.assertFalse(notify('https://visa.vfsglobal.com/', ['email', 'whatsapp', 'whatsapp']))
            whatsapp.assert_called_once()
            self.assertIn('Possível disponibilidade', output.call_args_list[0].args[0])

    def test_whatsapp_template_request(self):
        values = dict(WHATSAPP_TOKEN='test-only', WHATSAPP_PHONE_NUMBER_ID='123',
                      WHATSAPP_TO='244900000000', WHATSAPP_TEMPLATE='test_alert',
                      WHATSAPP_TEMPLATE_LANGUAGE='pt_PT', WHATSAPP_API_VERSION='v23.0')
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"messages":[{"id":"test"}]}'
        with patch.dict('os.environ', values, clear=True), patch('bootvfs.urlopen', return_value=response) as send:
            send_whatsapp()
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, 'https://graph.facebook.com/v23.0/123/messages')
            self.assertEqual(json.loads(request.data)['template']['name'], 'test_alert')

    def test_observed_states(self):
        yes, no = ["Appointment available"], ["No appointments"]
        cases = {
            "Appointment   available": "possible",
            "No appointments": "unavailable",
            "Appointment available. No appointments": "unknown",
            "Sign in. Appointment available": "manual",
            "CAPTCHA": "manual",
            "Book an appointment": "unknown",
            "": "unknown",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify(text, yes, no), expected)

    def test_configuration_guardrails(self):
        base = {"available_text": ["Slot available"], "unavailable_text": ["No slots"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for override in ({"url": "https://vfsglobal.com.evil.example/"},
                             {"interval_seconds": 1}, {"available_text": []}):
                path.write_text(json.dumps(base | override))
                with self.assertRaises(ValueError):
                    load_config(path)
            path.write_text(json.dumps(base))
            self.assertEqual(load_config(path)["interval_seconds"], 900)


if __name__ == "__main__":
    unittest.main()
