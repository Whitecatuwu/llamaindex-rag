import unittest

from src.classification.infrastructure.state.classification_state_store import ClassificationStateStore
from tests.utils.tempdir import managed_temp_dir


class ClassificationStateStoreTests(unittest.TestCase):
    def test_create_with_recovery_rebuilds_corrupted_db(self):
        with managed_temp_dir("state_store_corrupt") as tmp_path:
            db_path = tmp_path / "classification_state.db"
            db_path.write_text("not a sqlite file", encoding="utf-8")

            store, recovered, backup = ClassificationStateStore.create_with_recovery(str(db_path))
            try:
                self.assertTrue(recovered)
                self.assertIsNotNone(backup)
                store.upsert(
                    state_key="1",
                    source_mode="html",
                    last_revid=1,
                    content_hash="h1",
                    strategy_version="1.0.0",
                    entity_type="cat",
                    source_path="memory://1",
                )
                state = store.get("1")
                self.assertIsNotNone(state)
                self.assertEqual(state.last_revid, 1)
            finally:
                store.close()

    def test_create_with_recovery_without_corruption(self):
        with managed_temp_dir("state_store_normal") as tmp_path:
            db_path = tmp_path / "classification_state.db"
            store, recovered, backup = ClassificationStateStore.create_with_recovery(str(db_path))
            try:
                self.assertFalse(recovered)
                self.assertIsNone(backup)
            finally:
                store.close()
