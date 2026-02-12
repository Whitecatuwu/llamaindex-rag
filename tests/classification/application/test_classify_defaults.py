import unittest
from unittest.mock import MagicMock, patch

from src.classification.classify import run_classify


class ClassifyDefaultsTests(unittest.TestCase):
    def test_run_classify_default_db_path_points_to_artifacts_registry(self):
        source = MagicMock()
        source.discover.return_value = []

        with (
            patch("src.classification.classify.RegistryPageSource", return_value=source) as registry_source_ctor,
            patch("src.classification.classify.ClassificationPipeline") as pipeline_ctor,
            patch("src.classification.classify.ClassifyWikiPagesUseCase") as use_case_ctor,
        ):
            use_case = MagicMock()
            use_case.execute.return_value = MagicMock()
            use_case_ctor.return_value = use_case
            pipeline_ctor.return_value = MagicMock()

            run_classify(
                enable_classification=True,
                source_mode="db",
                incremental=False,
                full_rebuild=False,
            )

        registry_source_ctor.assert_called_once_with(db_path="artifacts/raw/wiki/wiki_registry.db")

