import json
import sqlite3
import unittest
from pathlib import Path


CATALOG = Path(__file__).resolve().parents[1] / "app" / "data" / "dialogue_practice_catalog.sqlite3"
REPORT = Path(__file__).resolve().parents[1] / "app" / "data" / "dialogue_practice_catalog.report.json"


class PracticeCatalogIntegrityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(f"file:{CATALOG.as_posix()}?mode=ro", uri=True)

    def tearDown(self) -> None:
        self.connection.close()

    def test_curated_catalog_is_limited_licensed_and_safe(self) -> None:
        metadata = dict(self.connection.execute("SELECT key, value FROM metadata"))
        self.assertEqual(metadata["schema_version"], "practice-materials.v1")
        self.assertEqual(metadata["source_dataset"], "RealPersonaChat")
        self.assertEqual(metadata["source_license"], "CC BY-SA 4.0")
        self.assertEqual(metadata["source_license_status"], "verified_from_local_license")
        self.assertEqual(self.connection.execute("SELECT COUNT(*) FROM materials").fetchone()[0], 624)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(DISTINCT category_code) FROM materials"
        ).fetchone()[0], 8)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(DISTINCT scene_code) FROM materials"
        ).fetchone()[0], 55)
        self.assertLessEqual(self.connection.execute(
            "SELECT MAX(total) FROM (SELECT COUNT(*) AS total FROM materials GROUP BY scene_code)"
        ).fetchone()[0], 20)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM materials WHERE source_dataset <> 'RealPersonaChat'"
        ).fetchone()[0], 0)
        columns = {row[1] for row in self.connection.execute("PRAGMA table_info(materials)")}
        self.assertFalse(columns & {"persona", "demographics", "speaker", "speaker_id", "review_status"})
        for (context_json,) in self.connection.execute("SELECT context_json FROM materials"):
            self.assertLessEqual(len(context_json), 1600)
            self.assertNotIn("speaker_1", context_json)
            self.assertNotIn("speaker_2", context_json)

    def test_report_matches_database_and_declares_exclusions(self) -> None:
        report = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(report["counts"]["selected_materials"], 624)
        self.assertTrue(all(value is False for value in report["safety"].values()))
        database_counts = dict(self.connection.execute(
            "SELECT scene_code, COUNT(*) FROM materials GROUP BY scene_code"
        ))
        self.assertEqual(report["scene_counts"], database_counts)


if __name__ == "__main__":
    unittest.main()
