import logging
import os

logger = logging.getLogger(__name__)
_initialized = False


def _init_firebase():
    global _initialized
    if _initialized:
        return
    cred_path = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    if not cred_path:
        logger.warning("FIREBASE_CREDENTIALS_JSON not set — push disabled")
        return
    try:
        import firebase_admin
        from firebase_admin import credentials
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        _initialized = True
    except Exception as e:
        logger.error(f"Firebase init failed: {e}")


def send_push(fcm_token: str, title: str, body: str, data: dict | None = None) -> bool:
    _init_firebase()
    if not _initialized:
        return False
    try:
        from firebase_admin import messaging
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            token=fcm_token,
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"FCM push failed for token {fcm_token[:20]}...: {e}")
        return False


def send_push_multicast(tokens: list[str], title: str, body: str, data: dict | None = None) -> int:
    _init_firebase()
    if not _initialized or not tokens:
        return 0
    try:
        from firebase_admin import messaging
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data={k: str(v) for k, v in (data or {}).items()},
            tokens=tokens,
        )
        resp = messaging.send_each_for_multicast(message)
        return resp.success_count
    except Exception as e:
        logger.error(f"FCM multicast failed: {e}")
        return 0
