import enum


class ClipType(str, enum.Enum):
    TALKING = "talking"
    BROLL = "broll"
    REMIX = "remix"


class AssetType(str, enum.Enum):
    MUSIC = "music"
    SFX = "sfx"


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    TRANSCRIBING = "transcribing"
    CLASSIFYING = "classifying"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"


class IntakeMode(str, enum.Enum):
    UPLOAD = "upload"
    WATCH = "watch"
    API = "api"


class AutonomyMode(str, enum.Enum):
    SUPERVISED = "supervised"
    REVIEW_THEN_PUBLISH = "review_then_publish"
    AUTO_PUBLISH = "auto_publish"


class ReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "pending_review"
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


class WorkspaceLifecycle(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class PlatformType(str, enum.Enum):
    YOUTUBE = "youtube"
    TIKTOK = "tiktok"
    INSTAGRAM_REELS = "instagram_reels"
    LINKEDIN = "linkedin"
    X = "x"


class CredentialSource(str, enum.Enum):
    PLATFORM = "platform"
    BYOK = "byok"


class AIProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    VERTEX = "vertex"
    GEMINI = "gemini"
    DEEPGRAM = "deepgram"
    DASHSCOPE = "dashscope"


class AIUsageStatus(str, enum.Enum):
    SUCCESS = "success"
    ERROR = "error"


class SubscriptionStatus(str, enum.Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    GRACE_PERIOD = "grace_period"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


class ComplianceExportStatus(str, enum.Enum):
    REQUESTED = "requested"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
