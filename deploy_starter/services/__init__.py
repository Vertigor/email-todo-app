"""
业务逻辑服务模块
"""
from .email_sync import (
    sync_emails_internal,
    sync_emails_with_progress,
    get_email_config,
    save_email_config,
)
from .email_forward import (
    get_smtp_config,
    save_smtp_config,
    forward_email,
    process_forwarding_for_email,
)

__all__ = [
    "sync_emails_internal",
    "sync_emails_with_progress",
    "get_email_config",
    "save_email_config",
    "get_smtp_config",
    "save_smtp_config",
    "forward_email",
    "process_forwarding_for_email",
]
