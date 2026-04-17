from domain.shared.enums import (
    AIProvider,
    AIUsageStatus,
    AssetType,
    AutonomyMode,
    ClipType,
    ComplianceExportStatus,
    CredentialSource,
    IntakeMode,
    InvoiceStatus,
    JobStatus,
    PlatformType,
    ProcessingStatus,
    ReviewStatus,
    SubscriptionStatus,
    WorkspaceLifecycle,
)
from domain.shared.ids import UUID_LENGTH, UUID_SQL_TYPE, new_uuid


def enum_values(enum_cls):
    return [item.value for item in enum_cls]


ENUM_SQL_OPTIONS = {
    "native_enum": False,
    "values_callable": enum_values,
}

__all__ = [
    "AIProvider",
    "AIUsageStatus",
    "AssetType",
    "AutonomyMode",
    "ClipType",
    "ComplianceExportStatus",
    "CredentialSource",
    "IntakeMode",
    "InvoiceStatus",
    "JobStatus",
    "PlatformType",
    "ProcessingStatus",
    "ReviewStatus",
    "SubscriptionStatus",
    "UUID_LENGTH",
    "UUID_SQL_TYPE",
    "WorkspaceLifecycle",
    "new_uuid",
    "ENUM_SQL_OPTIONS",
]
