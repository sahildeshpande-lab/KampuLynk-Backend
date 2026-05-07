import os
from html import escape
from pathlib import Path

from ..config import load_env_files

load_env_files()


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
BRAND_COLORS = {
    "crimson": "#E13C4B",
    "deep_navy": "#001E2D",
    "dark_navy": "#000F1E",
    "navy_blue": "#001E3C",
    "medium_blue": "#002D4B",
    "steel_blue": "#1C4587",
    "light_gray": "#E1E1E1",
    "dark_gray": "#4B4B4B",
    "black": "#000000",
}


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL")

    if not api_key or not from_email:
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except Exception:
        return False

    try:
        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )
        client = SendGridAPIClient(api_key)
        response = client.send(message)
        return 200 <= response.status_code < 300
    except Exception:
        return False


def _load_template(template_name: str) -> str:
    return (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")


def _render_template(template_name: str, context: dict[str, object], raw_keys: set[str] | None = None) -> str:
    rendered = _load_template(template_name)
    raw_keys = raw_keys or set()
    for key, value in {**BRAND_COLORS, **context}.items():
        replacement = str(value) if key in raw_keys else escape(str(value))
        rendered = rendered.replace(f"{{{{{key}}}}}", replacement)
    return rendered


def _render_email_layout(title: str, body_html: str) -> str:
    # Use BASE_URL from env, default to localhost for development
    base_url = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
    # Ensure logo exists in the expected location
    static_dir = Path(__file__).resolve().parents[1] / "static"
    logo_path = static_dir / "logo.jpg"
    
    # Note: If BASE_URL is localhost, images will not render in remote email clients (Gmail, etc.)
    # For production, BASE_URL should be a public HTTPS URL.
    logo_url = f"{base_url}/static/logo.jpg"
    
    return _render_template(
        "layouts/base_email.html",
        {"title": title, "body_html": body_html, "logo_url": logo_url},
        raw_keys={"body_html"},
    )


def _paragraphs(text: str) -> str:
    return "".join(f'<p style="margin:0 0 14px;">{escape(part)}</p>' for part in text.splitlines() if part.strip())


def build_otp_email_html(otp: str) -> str:
    body_html = _render_template("auth/otp_email.html", {"otp": otp})
    return _render_email_layout("Email Verification", body_html)


def _notification_template_name(notification_type: str) -> str:
    match notification_type:
        case "topic":
            return "notification_topic_email.html"
        case "broadcast":
            return "notification_broadcast_email.html"
        case "configuration":
            return "notification_configuration_email.html"
        case "resend-otp":
            return "notification_resend_otp_email.html"
        case _:
            return "notification_send_email.html"


def build_notification_email_html(
    title: str,
    body: str,
    html_body: str | None = None,
    notification_type: str = "send",
    template_name: str | None = None,
) -> str:
    notification_body = html_body if html_body else _paragraphs(body)
    selected_template = template_name or _notification_template_name(notification_type)
    body_html = _render_template(
        f"notifications/{selected_template}",
        {"notification_body": notification_body},
        raw_keys={"notification_body"},
    )
    return _render_email_layout(title, body_html)


def build_account_created_email_html(full_name: str | None = None) -> str:
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    body_html = _render_template("auth/account_created_email.html", {"greeting": greeting})
    return _render_email_layout("Account Created Successfully", body_html)


def build_password_changed_email_html(full_name: str | None = None) -> str:
    greeting = f"Hi {full_name}," if full_name else "Hi,"
    body_html = _render_template("auth/password_changed_email.html", {"greeting": greeting})
    return _render_email_layout("Password Changed Successfully", body_html)


def send_otp_email(to_email: str, otp: str) -> bool:
    return _send_email(to_email, "KampuLynk OTP Verification", build_otp_email_html(otp))


def send_account_created_email(to_email: str, full_name: str | None = None) -> bool:
    return _send_email(to_email, "KampuLynk Account Created", build_account_created_email_html(full_name))


def send_password_changed_email(to_email: str, full_name: str | None = None) -> bool:
    return _send_email(to_email, "KampuLynk Password Changed", build_password_changed_email_html(full_name))


def send_notification_email(
    to_email: str,
    subject: str,
    title: str,
    body: str,
    html_body: str | None = None,
    notification_type: str = "send",
    template_name: str | None = None,
) -> bool:
    return _send_email(
        to_email,
        subject,
        build_notification_email_html(title, body, html_body, notification_type, template_name),
    )
