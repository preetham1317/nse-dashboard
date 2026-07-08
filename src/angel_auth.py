import pyotp
from SmartApi import SmartConnect

from src import config
from src.logging_utils import get_logger

logger = get_logger(__name__)


class AngelAuthError(Exception):
    pass


def login() -> tuple[SmartConnect, dict]:
    """Log in to Angel One SmartAPI via client code + PIN + TOTP.

    Returns (smart_connect, session_data) where session_data has jwtToken/
    refreshToken/feedToken. Raises AngelAuthError on any failure - callers
    must not substitute a fallback session, per the no-silent-failure rule.
    """
    missing = [
        name
        for name, value in (
            ("ANGEL_API_KEY", config.ANGEL_API_KEY),
            ("ANGEL_CLIENT_ID", config.ANGEL_CLIENT_ID),
            ("ANGEL_PIN", config.ANGEL_PIN),
            ("ANGEL_TOTP_SECRET", config.ANGEL_TOTP_SECRET),
        )
        if not value
    ]
    if missing:
        raise AngelAuthError(f"missing required env vars: {', '.join(missing)}")

    smart_connect = SmartConnect(api_key=config.ANGEL_API_KEY)
    totp = pyotp.TOTP(config.ANGEL_TOTP_SECRET).now()

    session = smart_connect.generateSession(config.ANGEL_CLIENT_ID, config.ANGEL_PIN, totp)
    if not session or not session.get("status"):
        message = session.get("message") if session else "no response"
        raise AngelAuthError(f"login failed: {message}")

    logger.info("Angel One login succeeded for client_id=%s", config.ANGEL_CLIENT_ID)
    return smart_connect, session["data"]


if __name__ == "__main__":
    conn, session_data = login()
    profile = conn.getProfile(session_data["refreshToken"])
    logger.info("profile check: %s", profile.get("data", {}).get("name"))
