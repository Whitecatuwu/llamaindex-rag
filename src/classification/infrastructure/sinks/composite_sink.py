from src.classification.application.contracts import ClassificationLabelRecord
from src.classification.application.ports import ClassificationSinkPort


class CompositeClassificationSink(ClassificationSinkPort):
    def __init__(self, primary: ClassificationSinkPort, secondary: ClassificationSinkPort) -> None:
        self.primary = primary
        self.secondary = secondary

    def write_label(self, row: ClassificationLabelRecord) -> None:
        self.primary.write_label(row)
        self.secondary.write_label(row)

    def write_review(self, row: ClassificationLabelRecord) -> None:
        self.primary.write_review(row)
        self.secondary.write_review(row)

    def close(self) -> None:
        try:
            self.primary.close()
        finally:
            self.secondary.close()
