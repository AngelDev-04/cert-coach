"""Unit tests for exam registry, blueprints, and catalogs."""

from __future__ import annotations

import unittest

from cert_coach.core.models import ExamType
from cert_coach.exams.registry import ExamRegistry


class ExamRegistryTests(unittest.TestCase):
    def test_list_exams_returns_all_three(self) -> None:
        exams = ExamRegistry.list_exams()
        codes = [e.code for e in exams]
        self.assertIn("SAA-C03", codes)
        self.assertIn("CLF-C02", codes)
        self.assertIn("AIF-C01", codes)

    def test_get_metadata_by_enum_and_string(self) -> None:
        meta1 = ExamRegistry.get_metadata(ExamType.SAA_C03)
        meta2 = ExamRegistry.get_metadata("saa-c03")
        self.assertEqual(meta1.code, "SAA-C03")
        self.assertEqual(meta2.code, "SAA-C03")
        self.assertEqual(meta1.domains_count, 4)
        self.assertEqual(meta1.tasks_count, 14)

    def test_get_unknown_exam_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            ExamRegistry.get_metadata("invalid-exam")

    def test_saa_c03_catalog_has_valid_weights(self) -> None:
        catalog = ExamRegistry.get_catalog("saa-c03")
        self.assertEqual(catalog["exam_code"], "SAA-C03")
        total_weight = sum(d["weight"] for d in catalog["domains"])
        self.assertEqual(total_weight, 100)

    def test_clf_c02_catalog_has_valid_weights(self) -> None:
        catalog = ExamRegistry.get_catalog("clf-c02")
        self.assertEqual(catalog["exam_code"], "CLF-C02")
        total_weight = sum(d["weight"] for d in catalog["domains"])
        self.assertEqual(total_weight, 100)
        self.assertEqual(len(catalog["domains"]), 4)

    def test_aif_c01_catalog_has_valid_weights(self) -> None:
        catalog = ExamRegistry.get_catalog("aif-c01")
        self.assertEqual(catalog["exam_code"], "AIF-C01")
        total_weight = sum(d["weight"] for d in catalog["domains"])
        self.assertEqual(total_weight, 100)
        self.assertEqual(len(catalog["domains"]), 5)

    def test_blueprint_markdown_generation(self) -> None:
        for exam in ("saa-c03", "clf-c02", "aif-c01"):
            md = ExamRegistry.get_blueprint_markdown(exam)
            self.assertIn("#", md)
            self.assertIn("Domain", md)


if __name__ == "__main__":
    unittest.main()
