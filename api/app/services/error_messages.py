"""
User-facing error messages and retry advice for AI service failures.
Keyed by error code from _classify_error() in agent_service.py.

# TODO: If this product moves to a paid Gemini tier, update quota_exhausted
# user_message and retry_advice — "wait_24h" is specific to free-tier daily limits.
"""

_ALL_EXHAUSTED = (
    "All AI providers have reached their daily free-tier limit. "
    "Limits reset at midnight UTC — please try again in up to 24 hours."
)

USER_MESSAGES: dict[str, str] = {
    "quota_exhausted":        "The AI service has reached its daily limit. Please try again tomorrow.",
    "rate_limited":           "You're sending messages too quickly. Wait a moment and try again.",
    "service_unavailable":    "The AI service is temporarily unavailable. Please try again shortly.",
    "invalid_request":        "The AI couldn't process this request. Try shortening or removing attachments.",
    "auth_failure":           "There's a configuration issue with the AI service. Contact your administrator.",
    "unknown":                "Something went wrong with the AI service. Please try again.",
    "all_providers_exhausted": _ALL_EXHAUSTED,
}

RETRY_ADVICE: dict[str, str] = {
    "quota_exhausted":        "wait_24h",
    "rate_limited":           "wait_1m",
    "service_unavailable":    "retry_now",
    "invalid_request":        "edit_request",
    "auth_failure":           "contact_admin",
    "unknown":                "retry_now",
    "all_providers_exhausted": "wait_24h",
}
