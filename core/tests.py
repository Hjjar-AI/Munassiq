"""Core tests do not create a database."""
import os
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from config.environment import boolean, csv


class ConfigurationTests(SimpleTestCase):
    def test_invalid_boolean_is_rejected(self):
        with patch.dict(os.environ, {"CHECK_BOOLEAN": "maybe"}):
            with self.assertRaises(ImproperlyConfigured):
                boolean("CHECK_BOOLEAN")

    def test_explicit_false(self):
        with patch.dict(os.environ, {"CHECK_BOOLEAN": "false"}):
            self.assertFalse(boolean("CHECK_BOOLEAN", True))

    def test_list_discards_empty_entries(self):
        with patch.dict(os.environ, {"CHECK_LIST": "one, ,two"}):
            self.assertEqual(csv("CHECK_LIST"), ["one", "two"])


class CoreEndpointTests(SimpleTestCase):
    def test_health_is_public_and_database_independent(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "munassiq"})

    def test_health_rejects_mutation(self):
        self.assertEqual(self.client.post("/api/v1/health/").status_code, 405)

    def test_schema_is_available(self):
        response = self.client.get("/api/v1/schema/?format=json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("/api/v1/health/", response.json()["paths"])

    def test_documentation_page_is_available(self):
        self.assertEqual(self.client.get("/api/v1/docs/").status_code, 200)
