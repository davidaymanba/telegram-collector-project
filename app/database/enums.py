from enum import StrEnum


class FileStatus(StrEnum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    DUPLICATE = "duplicate"
    PROCESSING = "processing"
    CLASSIFIED = "classified"
    UNCLASSIFIED = "unclassified"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class ProcessingLogStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class ClassificationStatus(StrEnum):
    CLASSIFIED = "classified"
    UNCLASSIFIED = "unclassified"


class RunKind(StrEnum):
    COLLECT = "collect"
    PROCESS = "process"


class RunTrigger(StrEnum):
    CLI = "cli"
    WEB = "web"
    LAUNCHD = "launchd"


class ChannelStatus(StrEnum):
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    DISABLED = "disabled"


class ContentType(StrEnum):
    LECTURE = "lecture"
    PREVIOUS_EXAM = "previous_exam"
    ASSIGNMENT = "assignment"
    ANSWER_MODEL = "answer_model"
    SUMMARY = "summary"


CONTENT_TYPES: tuple[str, ...] = tuple(c.value for c in ContentType)
