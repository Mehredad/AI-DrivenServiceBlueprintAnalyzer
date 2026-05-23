"""
Transactional email via Resend (https://resend.com).
All functions are best-effort — errors are logged and never raised.
"""
import logging
import httpx
from app.config import get_settings

log = logging.getLogger(__name__)

_RESEND_ENDPOINT = "https://api.resend.com/emails"


async def send_welcome_email(to_email: str, full_name: str) -> None:
    s = get_settings()
    if not s.resend_api_key:
        log.debug("RESEND_API_KEY not configured — skipping welcome email to %s", to_email)
        return

    name = full_name.strip() or to_email.split("@")[0]
    app_url = (s.app_url or "https://blueprint-ai-v1-staging.vercel.app").rstrip("/")

    html = f"""\
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f9f9f9;font-family:'Inter',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td align="center" style="padding:40px 16px;">
<table width="520" cellpadding="0" cellspacing="0" border="0"
       style="background:#fff;border-radius:12px;border:1px solid #e5e5e5;padding:36px 32px;max-width:520px;">
  <tr><td>
    <div style="width:40px;height:40px;background:#111;border-radius:8px;display:flex;align-items:center;
                justify-content:center;margin-bottom:24px;">
      <svg width="18" height="18" viewBox="0 0 13 13" fill="none">
        <rect x="1" y="1" width="4.5" height="4.5" rx=".8" fill="white"/>
        <rect x="7" y="1" width="5"   height="4.5" rx=".8" fill="white" opacity=".6"/>
        <rect x="1" y="7.5" width="5" height="4.5" rx=".8" fill="white" opacity=".6"/>
        <rect x="7.5" y="7.5" width="4.5" height="4.5" rx=".8" fill="white" opacity=".28"/>
      </svg>
    </div>
    <h1 style="font-size:22px;font-weight:700;color:#111;margin:0 0 12px;line-height:1.3;">
      Welcome to Blueprint AI, {name}!
    </h1>
    <p style="font-size:15px;color:#555;line-height:1.7;margin:0 0 8px;">
      Your account is ready. Blueprint AI is a collaborative workspace for mapping
      end-to-end service journeys, designing AI capabilities, and aligning teams around
      how your service actually works.
    </p>
    <p style="font-size:15px;color:#555;line-height:1.7;margin:0 0 28px;">
      Sign in to create your first blueprint:
    </p>
    <a href="{app_url}"
       style="display:inline-block;background:#111;color:#fff;padding:12px 26px;
              border-radius:8px;text-decoration:none;font-weight:600;font-size:15px;
              letter-spacing:-.1px;">
      Open Blueprint AI →
    </a>
    <p style="font-size:12px;color:#aaa;margin-top:36px;margin-bottom:0;line-height:1.6;">
      You're receiving this because you created an account at Blueprint AI.<br>
      If you didn't sign up, you can safely ignore this email.
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

    text = (
        f"Welcome to Blueprint AI, {name}!\n\n"
        f"Your account is ready. Sign in to create your first blueprint:\n{app_url}\n\n"
        "If you didn't sign up, you can safely ignore this email."
    )

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.post(
                _RESEND_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {s.resend_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": s.from_email or "Blueprint AI <onboarding@resend.dev>",
                    "to": [to_email],
                    "subject": "Welcome to Blueprint AI!",
                    "html": html,
                    "text": text,
                },
            )
        if r.status_code >= 400:
            log.warning("Resend returned %d for welcome email to %s: %s", r.status_code, to_email, r.text[:200])
        else:
            log.info("Welcome email sent to %s (Resend id: %s)", to_email, r.json().get("id", "?"))
    except Exception as exc:
        log.warning("Failed to send welcome email to %s: %s", to_email, exc)
