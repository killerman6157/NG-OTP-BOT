import os

# Telegram Bot settings
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
GROUP_ID = int(os.environ.get("GROUP_ID"))
CHANNEL_LINK = os.environ.get("CHANNEL_LINK")
CHANNEL_NAME = os.environ.get("CHANNEL_NAME")

# ==========================================================
# IVASMS Login Credentials
# ==========================================================
LOGIN_URL = os.environ.get("LOGIN_URL")
LOGIN_EMAIL = os.environ.get("LOGIN_EMAIL")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD")

# IVASMS endpoints
BASE = "https://www.ivasms.com"
GET_SMS_URL = f"{BASE}/portal/sms/received/getsms"
GET_NUMBER_URL = f"{BASE}/portal/sms/received/getsms/number"
GET_OTP_URL = f"{BASE}/portal/sms/received/getsms/number/sms"

# ==========================================================
# Session and CSRF token (leave these as they are)
# ==========================================================
SESSION_COOKIE = ""
CSRF_TOKEN = ""

# Request headers (don't change unless necessary)
HEADERS = {
    "Origin": "https://www.ivasms.com",
    "Referer": "https://www.ivasms.com/portal/sms/received",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01"
}

# Polling interval (seconds)
FETCH_INTERVAL = 6

# DB file
DB_FILE = "otps_and_errors.db"

# ==========================================================
# Country and Service Mappings
# ==========================================================
COUNTRY_FLAGS = {
    "234": "🇳🇬 Nigeria",
    "880": "🇧🇩 Bangladesh",
    "51": "🇵🇪 Peru",
    "225": "🇨🇮 Ivory Coast",
    "20": "🇪🇬 Egypt",
    "255": "🇹🇿 Tanzania",
    "44": "🇬🇧 United Kingdom",
    "58": "🇻🇪 Venezuela",
    "996": "🇰🇬 Kyrgyzstan",
    "593": "🇪🇨 Ecuador",
    "591": "🇧🇴 Bolivia",
    "228": "🇹🇬 Togo",
    "221": "🇸🇳 Senegal",
    "1": "🇺🇸 United States",
    "970": "🇵🇸 Palestine",
    "98": "🇮🇷 Iran",
    "964": "🇮🇶 Iraq",
    "966": "🇸🇦 Saudi Arabia",
    "236": "🇨🇫 Central African Republic",
    "93": "🇦🇫 Afghanistan",
    "261": "🇲🇬 Madagascar",
    "977": "🇳🇵 Nepal",
    "967": "🇾🇪 Yemen",
    "998": "🇺🇿 Uzbekistan",
    "216": "🇹🇳 Tunisia",
    "963": "🇸🇾 Syria"
}

# An ƙara wasu kalmomi don gane sabis da kyau
SERVICES = {
    "whatsapp": "WhatsApp",
    "facebook": "Facebook",
    "meta": "Facebook",
    "fb": "Facebook",
    "telegram": "Telegram",
    "google": "Google",
    "instagram": "Instagram",
    "signal": "Signal",
    "snapchat": "Snapchat",
    "tiktok": "Tiktok",
    "twitter": "Twitter",
    "premierbet": "Premier Bet",
    "premier bet": "Premier Bet"
}

# Masking rule: keep first N chars then **** then last M chars
MASK_PREFIX_LEN = 7
MASK_SUFFIX_LEN = 3
