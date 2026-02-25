#!/usr/bin/env python3
"""
IPRegion — determines your IP geolocation using various GeoIP services and popular websites.
Python port of https://github.com/vernette/ipregion
"""

import argparse
import contextlib
import json
import os
import re
import random
import socket
import ssl
import subprocess
import sys
import threading
import time
import http.client
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from gzip import GzipFile

# ─── Constants ──────────────────────────────────────────────────────────────────

SCRIPT_NAME = "ipregion.py"
SCRIPT_URL = "https://github.com/deathnoragami/ipregion"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"

SPOTIFY_API_KEY = "142b583129b2df829de3656f9eb484e6"
SPOTIFY_CLIENT_ID = "9a8d2f0ce77a4e248bb71fefcb557637"
NETFLIX_API_KEY = "YXNkZmFzZGxmbnNkYWZoYXNkZmhrYWxm"
TWITCH_CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"
CHATGPT_STATSIG_API_KEY = "client-zUdXdSTygXJdzoE0sWTkP8GKTVsUMF2IRM7ShVO2JAG"
REDDIT_BASIC_ACCESS_TOKEN = "b2hYcG9xclpZdWIxa2c6"
YOUTUBE_SOCS_COOKIE = "CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjUwNzMwLjA1X3AwGgJlbiACGgYIgPC_xAY"
DISNEY_PLUS_API_KEY = "ZGlzbmV5JmFuZHJvaWQmMS4wLjA.bkeb0m230uUhv8qrAXuNu39tbE_mD5EEhM_NAcohjyA"
DISNEY_PLUS_JSON_BODY = json.dumps({
    "query": "\n     mutation registerDevice($registerDevice: RegisterDeviceInput!) {\n       registerDevice(registerDevice: $registerDevice) {\n         __typename\n       }\n     }\n     ",
    "variables": {
        "registerDevice": {
            "applicationRuntime": "android",
            "attributes": {
                "operatingSystem": "Android",
                "operatingSystemVersion": "13"
            },
            "deviceFamily": "android",
            "deviceLanguage": "en",
            "deviceProfile": "phone",
            "devicePlatformId": "android"
        }
    },
    "operationName": "registerDevice"
})

# ─── Status Constants ───────────────────────────────────────────────────────────

STATUS_NA = "N/A"
STATUS_DENIED = "Denied"
STATUS_RATE_LIMIT = "Rate-limit"
STATUS_SERVER_ERROR = "Server error"

STATUS_STRINGS = {STATUS_NA, STATUS_DENIED, STATUS_RATE_LIMIT, STATUS_SERVER_ERROR}

# ─── ANSI Colors ────────────────────────────────────────────────────────────────

# Enable ANSI on Windows
if sys.platform == "win32":
    os.system("")

COLORS = {
    "HEADER":       "\033[1;36m",
    "SERVICE":      "\033[1;32m",
    "HEART":        "\033[1;31m",
    "URL":          "\033[1;90m",
    "ASN":          "\033[1;33m",
    "TABLE_HEADER": "\033[1;97m",
    "TABLE_VALUE":  "\033[1m",
    "NULL":         "\033[0;90m",
    "ERROR":        "\033[1;31m",
    "WARN":         "\033[1;33m",
    "INFO":         "\033[1;36m",
    "RESET":        "\033[0m",
}


def color(name: str, text: str) -> str:
    code = COLORS.get(name, COLORS["RESET"])
    return f"{code}{text}\033[0m"


def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m"


# ─── Primary Services ──────────────────────────────────────────────────────────

# Format: "display_name|domain|url_template|response_format"
# response_format: "json" (default) or "plain"
PRIMARY_SERVICES = {
    "MAXMIND":        "maxmind.com|geoip.maxmind.com|/geoip/v2.1/city/me",
    "RIPE":           "rdap.db.ripe.net|rdap.db.ripe.net|/ip/{ip}",
    "IPINFO_IO":      "ipinfo.io|ipinfo.io|/widget/demo/{ip}",
    "IPREGISTRY":     "ipregistry.co|api.ipregistry.co|/{ip}?hostname=true&key=sb69ksjcajfs4c",
    "IPAPI_CO":       "ipapi.co|ipapi.co|/{ip}/json",
    "CLOUDFLARE":     "cloudflare.com|www.cloudflare.com|/cdn-cgi/trace|plain",
    "IPLOCATION_COM": "iplocation.com|iplocation.com",
    "COUNTRY_IS":     "country.is|api.country.is|/{ip}",
    "GEOAPIFY_COM":   "geoapify.com|api.geoapify.com|/v1/ipinfo?&ip={ip}&apiKey=b8568cb9afc64fad861a69edbddb2658",
    "GEOJS_IO":       "geojs.io|get.geojs.io|/v1/ip/country.json?ip={ip}",
    "IPAPI_IS":       "ipapi.is|api.ipapi.is|/?q={ip}",
    "IPBASE_COM":     "ipbase.com|api.ipbase.com|/v2/info?ip={ip}",
    "IPQUERY_IO":     "ipquery.io|api.ipquery.io|/{ip}",
    "IPWHO_IS":       "ipwho.is|ipwho.is|/{ip}",
    "IPAPI_COM":      "ip-api.com|demo.ip-api.com|/json/{ip}?fields=countryCode",
    "2IP":            "2ip.io|api.2ip.io",
}

PRIMARY_SERVICES_ORDER = [
    "MAXMIND", "RIPE", "IPINFO_IO", "CLOUDFLARE", "IPREGISTRY",
    "IPAPI_CO", "IPLOCATION_COM", "COUNTRY_IS", "GEOAPIFY_COM",
    "GEOJS_IO", "IPAPI_IS", "IPBASE_COM", "IPQUERY_IO",
    "IPWHO_IS", "IPAPI_COM", "2IP",
]

# Custom handlers for primary services that need special logic
PRIMARY_CUSTOM_HANDLERS = {"CLOUDFLARE", "IPLOCATION_COM", "2IP"}

SERVICE_HEADERS = {
    "IPREGISTRY": {"Origin": "https://ipregistry.co"},
    "MAXMIND":    {"Referer": "https://www.maxmind.com"},
    "IPAPI_COM":  {"Origin": "https://ip-api.com"},
}

# JSON extraction paths for each primary service
JQ_FILTERS = {
    "MAXMIND":        ["country", "iso_code"],
    "RIPE":           ["country"],
    "IPINFO_IO":      ["data", "country"],
    "IPREGISTRY":     ["location", "country", "code"],
    "IPAPI_CO":       ["country"],
    "COUNTRY_IS":     ["country"],
    "GEOAPIFY_COM":   ["country", "iso_code"],
    "GEOJS_IO":       [0, "country"],
    "IPAPI_IS":       ["location", "country_code"],
    "IPBASE_COM":     ["data", "location", "country", "alpha2"],
    "IPQUERY_IO":     ["location", "country_code"],
    "IPWHO_IS":       ["country_code"],
    "IPAPI_COM":      ["countryCode"],
    "2IP":            ["code"],
}

# Custom services
CUSTOM_SERVICES = {
    "GOOGLE": "Google",
    "GOOGLE_SEARCH_CAPTCHA": "Google Search Captcha",
    "YOUTUBE": "YouTube",
    "YOUTUBE_PREMIUM": "YouTube Premium",
    "YOUTUBE_MUSIC": "YouTube Music",
    "TWITCH": "Twitch",
    "CHATGPT": "ChatGPT",
    "NETFLIX": "Netflix",
    "SPOTIFY": "Spotify",
    "SPOTIFY_SIGNUP": "Spotify Signup",
    "DEEZER": "Deezer",
    "REDDIT": "Reddit",
    "REDDIT_GUEST_ACCESS": "Reddit (Guest Access)",
    "AMAZON_PRIME": "Amazon Prime",
    "APPLE": "Apple",
    "STEAM": "Steam",
    "PLAYSTATION": "PlayStation",
    "TIKTOK": "Tiktok",
    "OOKLA_SPEEDTEST": "Ookla Speedtest",
    "JETBRAINS": "JetBrains",
    "BING": "Microsoft (Bing)",
}

CUSTOM_SERVICES_ORDER = [
    "GOOGLE", "GOOGLE_SEARCH_CAPTCHA", "YOUTUBE", "YOUTUBE_PREMIUM",
    "YOUTUBE_MUSIC", "TWITCH", "CHATGPT", "NETFLIX", "SPOTIFY",
    "SPOTIFY_SIGNUP", "DEEZER", "REDDIT", "REDDIT_GUEST_ACCESS",
    "AMAZON_PRIME", "APPLE", "STEAM", "PLAYSTATION", "TIKTOK",
    "OOKLA_SPEEDTEST", "JETBRAINS", "BING",
]

CDN_SERVICES = {
    "YOUTUBE_CDN":  "YouTube CDN",
    "NETFLIX_CDN":  "Netflix CDN",
}

CDN_SERVICES_ORDER = ["YOUTUBE_CDN", "NETFLIX_CDN"]

EXCLUDED_SERVICES = {"GOOGLE_SEARCH_CAPTCHA"}

IPV6_OVER_IPV4_SERVICES = {
    "IPINFO_IO", "IPAPI_IS", "IPLOCATION_COM", "IPWHO_IS", "IPAPI_COM",
}

IDENTITY_SERVICES_V4 = [
    "api4.ipify.org", "ipv4.icanhazip.com", "v4.ident.me",
    "ifconfig.me", "ident.me",
]

IDENTITY_SERVICES_V6 = [
    "api6.ipify.org", "ipv6.icanhazip.com", "v6.ident.me",
    "ifconfig.me", "ident.me",
]


# ─── Global State ───────────────────────────────────────────────────────────────

class State:
    verbose = False
    json_output = False
    groups_to_show = "all"
    timeout = 5
    ipv4_only = False
    ipv6_only = False
    proxy_addr = ""
    proxy_type = ""  # "http" or "socks5"

    ipv4_supported = False
    ipv6_supported = False
    external_ipv4 = ""
    external_ipv6 = ""
    asn = ""
    asn_name = ""

    results_primary = []  # list of (service, ipv4, ipv6)
    results_custom = []
    results_cdn = []

    spinner_text = ""
    spinner_running = False


state = State()


# ─── Logging ────────────────────────────────────────────────────────────────────

def log(level: str, message: str):
    if not state.verbose:
        return
    ts = time.strftime("%d.%m.%Y %H:%M:%S")
    color_map = {"ERROR": "ERROR", "WARNING": "WARN", "INFO": "INFO"}
    c = color_map.get(level, "RESET")
    print(f"[{ts}] [{color(c, level)}]: {message}", file=sys.stderr)


# ─── Spinner ────────────────────────────────────────────────────────────────────

class Spinner:
    def __init__(self):
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        if state.json_output or state.verbose:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def _spin(self):
        chars = "|/-\\"
        i = 0
        while not self._stop_event.is_set():
            ch = chars[i % len(chars)]
            text = state.spinner_text or ""
            line = f"\r\033[K{color('HEADER', ch)} {color('HEADER', 'Checking:')} {color('SERVICE', text)}"
            sys.stderr.write(line)
            sys.stderr.flush()
            i += 1
            self._stop_event.wait(0.1)

    def stop(self):
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=2)
        sys.stderr.write("\r\033[K")
        sys.stderr.flush()
        self._thread = None

    def update(self, text: str):
        state.spinner_text = text


spinner = Spinner()


# ─── SOCKS5 Support ────────────────────────────────────────────────────────────

def ensure_socks5_support():
    """Check if PySocks is available, offer to install if not."""
    try:
        import socks  # noqa: F401
        return True
    except ImportError:
        pass

    print(f"\n{color('WARN', 'SOCKS5 proxy requires the PySocks library, which is not installed.')}")
    print(f"{color('INFO', 'Do you want to install it? [y/N]:')} ", end="")
    
    try:
        response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        response = ""

    if response not in ("y", "yes"):
        print(f"{color('WARN', 'Installation canceled by user. Cannot use SOCKS5 proxy.')}")
        sys.exit(1)

    print(f"{color('INFO', 'Installing PySocks...')}")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pysocks"],
            stdout=subprocess.DEVNULL if not state.verbose else None,
        )
    except subprocess.CalledProcessError:
        print(f"{color('ERROR', 'Failed to install PySocks. Please install it manually: pip install pysocks')}")
        sys.exit(1)

    # Verify installation
    try:
        import socks  # noqa: F401
        print(f"{color('SERVICE', 'PySocks installed successfully!')}\n")
        return True
    except ImportError:
        print(f"{color('ERROR', 'PySocks installation failed.')}")
        sys.exit(1)


def setup_socks5_proxy(addr: str):
    """Configure global SOCKS5 proxy via PySocks monkey-patching."""
    import socks

    if ":" not in addr:
        print(f"{color('ERROR', f'Invalid proxy address: {addr}. Expected format: host:port')}")
        sys.exit(1)

    host, port_str = addr.rsplit(":", 1)
    try:
        port = int(port_str)
    except ValueError:
        print(f"{color('ERROR', f'Invalid proxy port: {port_str}')}")
        sys.exit(1)

    socks.set_default_proxy(socks.SOCKS5, host, port)
    socket.socket = socks.socksocket
    log("INFO", f"SOCKS5 proxy configured: {addr}")


# ─── Forced IP Version ─────────────────────────────────────────────────────────

_original_getaddrinfo = socket.getaddrinfo


@contextlib.contextmanager
def force_ip_version(version: int):
    """Context manager that forces socket to use only IPv4 or IPv6."""
    family = socket.AF_INET if version == 4 else socket.AF_INET6

    def filtered_getaddrinfo(*args, **kwargs):
        results = _original_getaddrinfo(*args, **kwargs)
        filtered = [r for r in results if r[0] == family]
        return filtered if filtered else results

    socket.getaddrinfo = filtered_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = _original_getaddrinfo


# ─── HTTP Client ────────────────────────────────────────────────────────────────

def http_request(
    method: str,
    url: str,
    headers: dict | None = None,
    data: bytes | None = None,
    json_body: str | None = None,
    user_agent: str | None = None,
    timeout: int | None = None,
    follow_redirects: bool = True,
) -> tuple[str, int]:
    """
    Make an HTTP request. Returns (response_body, http_status_code).
    """
    if timeout is None:
        timeout = state.timeout

    hdrs = {
        "User-Agent": user_agent or USER_AGENT,
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
    }
    if headers:
        hdrs.update(headers)

    if json_body is not None:
        data = json_body.encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)

    # HTTP proxy support (non-SOCKS5)
    opener_handlers = []
    if state.proxy_addr and state.proxy_type == "http":
        proxy_handler = urllib.request.ProxyHandler({
            "http": f"http://{state.proxy_addr}",
            "https": f"http://{state.proxy_addr}",
        })
        opener_handlers.append(proxy_handler)

    # SSL context that doesn't verify (like curl --insecure behavior for some services)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener_handlers.append(urllib.request.HTTPSHandler(context=ctx))

    opener = urllib.request.build_opener(*opener_handlers)

    try:
        resp = opener.open(req, timeout=timeout)
        body = resp.read()
        code = resp.getcode()

        # Handle gzip
        if resp.headers.get("Content-Encoding") == "gzip":
            body = GzipFile(fileobj=BytesIO(body)).read()

        return body.decode("utf-8", errors="replace"), code

    except urllib.error.HTTPError as e:
        body = ""
        try:
            raw = e.read()
            if e.headers.get("Content-Encoding") == "gzip":
                raw = GzipFile(fileobj=BytesIO(raw)).read()
            body = raw.decode("utf-8", errors="replace")
        except Exception:
            pass
        return body, e.code

    except (urllib.error.URLError, socket.timeout, OSError, Exception) as e:
        log("WARNING", f"Request failed for {url}: {e}")
        return "", 0


def http_head(url: str, headers: dict | None = None, timeout: int | None = None) -> tuple[dict, int]:
    """Make a HEAD request, return (response_headers_dict, status_code)."""
    if timeout is None:
        timeout = state.timeout

    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)

    req = urllib.request.Request(url, headers=hdrs, method="HEAD")

    opener_handlers = []
    if state.proxy_addr and state.proxy_type == "http":
        proxy_handler = urllib.request.ProxyHandler({
            "http": f"http://{state.proxy_addr}",
            "https": f"http://{state.proxy_addr}",
        })
        opener_handlers.append(proxy_handler)

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    opener_handlers.append(urllib.request.HTTPSHandler(context=ctx))

    opener = urllib.request.build_opener(*opener_handlers)

    try:
        resp = opener.open(req, timeout=timeout)
        resp_headers = {k.lower(): v for k, v in resp.getheaders()}
        return resp_headers, resp.getcode()
    except urllib.error.HTTPError as e:
        resp_headers = {k.lower(): v for k, v in e.headers.items()}
        return resp_headers, e.code
    except Exception as e:
        log("WARNING", f"HEAD request failed for {url}: {e}")
        return {}, 0


# ─── JSON Helpers ───────────────────────────────────────────────────────────────

def json_extract(data, path: list):
    """Extract nested value from parsed JSON using a path like ['country', 'iso_code']."""
    obj = data
    for key in path:
        if obj is None:
            return None
        if isinstance(key, int):
            if isinstance(obj, list) and len(obj) > key:
                obj = obj[key]
            else:
                return None
        elif isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
    return obj


def safe_json_parse(text: str):
    """Try to parse JSON, return None on failure."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


# ─── Status Helpers ─────────────────────────────────────────────────────────────

def is_status_string(value: str) -> bool:
    return value in STATUS_STRINGS


def status_from_http_code(code: int) -> str:
    if code == 403:
        return STATUS_DENIED
    elif code == 429:
        return STATUS_RATE_LIMIT
    elif 500 <= code < 600:
        return STATUS_SERVER_ERROR
    elif 400 <= code < 500:
        return STATUS_NA
    return ""


def format_value(value: str) -> str:
    if value == STATUS_NA:
        return color("NULL", value)
    elif value in (STATUS_DENIED, STATUS_SERVER_ERROR):
        return color("ERROR", value)
    elif value == STATUS_RATE_LIMIT:
        return color("WARN", value)
    else:
        return bold(value)


# ─── IP Helpers ─────────────────────────────────────────────────────────────────

def mask_ipv4(ip: str) -> str:
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.*.*"
    return ip


def mask_ipv6(ip: str) -> str:
    # Expand and mask: show first 3 groups
    try:
        full = socket.inet_ntop(socket.AF_INET6, socket.inet_pton(socket.AF_INET6, ip))
        parts = full.split(":")
        return f"{parts[0]}:{parts[1]}:{parts[2]}::"
    except Exception:
        parts = ip.split(":")
        return ":".join(parts[:3]) + "::"


# ─── IP Discovery ──────────────────────────────────────────────────────────────

def check_ip_support(version: int) -> bool:
    """Check if IPv4/IPv6 is supported."""
    spinner.update(f"IPv{version} support")
    log("INFO", f"Checking IPv{version} support")

    if version == 6 and not socket.has_ipv6:
        log("WARNING", "IPv6 not supported by OS")
        return False

    # Method 1: Try DNS resolution for both IPv4 and IPv6
    if version == 4:
        family = socket.AF_INET
    else:
        family = socket.AF_INET6

    try:
        results = socket.getaddrinfo("google.com", 443, family, socket.SOCK_STREAM)
        if results:
            log("INFO", f"IPv{version} DNS resolution works")
            # Try connecting to the resolved address
            for res in results[:2]:
                af, socktype, proto, canonname, sa = res
                try:
                    s = socket.socket(af, socktype, proto)
                    s.settimeout(3)
                    s.connect(sa)
                    s.close()
                    log("INFO", f"IPv{version} connectivity confirmed via {sa[0]}")
                    return True
                except (OSError, socket.timeout):
                    continue
    except (socket.gaierror, OSError):
        pass

    # Method 2: Try direct TCP connect to well-known HTTPS servers
    if version == 4:
        targets = [("8.8.8.8", 443), ("1.1.1.1", 443), ("9.9.9.9", 443)]
    else:
        targets = [
            ("2001:4860:4860::8888", 443),
            ("2606:4700:4700::1111", 443),
        ]

    for host, port in targets:
        try:
            s = socket.socket(family, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((host, port))
            s.close()
            log("INFO", f"IPv{version} connectivity confirmed via {host}")
            return True
        except (OSError, socket.timeout):
            continue

    log("WARNING", f"IPv{version} is not supported")
    return False


def fetch_external_ip(version: int) -> str:
    """Get external IP address from identity services."""
    spinner.update(f"External IPv{version} address")
    log("INFO", f"Getting external IPv{version} address")

    services = list(IDENTITY_SERVICES_V4 if version == 4 else IDENTITY_SERVICES_V6)
    random.shuffle(services)

    for service in services:
        try:
            url = f"https://{service}"
            with force_ip_version(version):
                body, code = http_request("GET", url, timeout=state.timeout)
            if not body or code not in (200, 0):
                log("WARNING", f"No valid response from {service} (code={code})")
                continue

            ip = body.strip().splitlines()[0].strip()

            if version == 4:
                m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', ip)
                if m:
                    ip = m.group(1)
                    log("INFO", f"IPv{version} from {service}: {ip}")
                    return ip
            elif version == 6 and ":" in ip:
                log("INFO", f"IPv{version} from {service}: {ip}")
                return ip
        except Exception as e:
            log("WARNING", f"Failed to get IP from {service}: {e}")

    log("ERROR", f"Failed to obtain IPv{version} address from any service")
    return ""


def discover_external_ips():
    if ipv4_enabled():
        state.external_ipv4 = fetch_external_ip(4)
    if ipv6_enabled():
        state.external_ipv6 = fetch_external_ip(6)

    if not state.external_ipv4 and not state.external_ipv6:
        print(f"{color('ERROR', '[ERROR]')} {bold('Failed to obtain external IPv4 and IPv6 address')}", file=sys.stderr)
        sys.exit(1)


def ipv4_enabled() -> bool:
    return not state.ipv6_only and state.ipv4_supported


def ipv6_enabled() -> bool:
    return not state.ipv4_only and state.ipv6_supported


def can_use_ipv4() -> bool:
    return ipv4_enabled() and bool(state.external_ipv4)


def can_use_ipv6() -> bool:
    return ipv6_enabled() and bool(state.external_ipv6)


def preferred_ip() -> str:
    return state.external_ipv4 if can_use_ipv4() else state.external_ipv6


# ─── ASN ────────────────────────────────────────────────────────────────────────

def get_asn():
    spinner.update("ASN info")
    log("INFO", "Getting ASN info")

    body, code = http_request(
        "GET", "https://geoip.maxmind.com/geoip/v2.1/city/me",
        headers={"Referer": "https://www.maxmind.com"},
    )

    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        traits = data.get("traits", {})
        state.asn = str(traits.get("autonomous_system_number", ""))
        state.asn_name = traits.get("autonomous_system_organization", "")
        log("INFO", f"ASN info: AS{state.asn} {state.asn_name}")


def get_registered_country(version: int) -> str:
    body, code = http_request(
        "GET", "https://geoip.maxmind.com/geoip/v2.1/city/me",
        headers={"Referer": "https://www.maxmind.com"},
    )
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        rc = data.get("registered_country", {})
        names = rc.get("names", {})
        return names.get("en", "")
    return ""


# ─── IATA Lookup ────────────────────────────────────────────────────────────────

def get_iata_location(iata_code: str) -> str:
    url = "https://www.air-port-codes.com/api/v1/single"
    body, code = http_request(
        "POST", url,
        headers={
            "APC-Auth": "96dc04b3fb",
            "Referer": "https://www.air-port-codes.com/",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=f"iata={iata_code}".encode("utf-8"),
    )
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        airport = data.get("airport", {})
        country = airport.get("country", {})
        return country.get("iso", "")
    return ""


# ─── Primary Service Probing ───────────────────────────────────────────────────

def probe_primary_service(service: str, ip: str) -> str:
    """Probe a primary GeoIP service and extract country code."""
    cfg = PRIMARY_SERVICES.get(service, "")
    parts = cfg.split("|")
    if len(parts) < 3:
        return STATUS_NA

    display_name = parts[0]
    domain = parts[1]
    url_template = parts[2]
    response_format = parts[3] if len(parts) > 3 else "json"

    url = f"https://{domain}{url_template.replace('{ip}', ip)}"

    hdrs = {}
    if service in SERVICE_HEADERS:
        hdrs.update(SERVICE_HEADERS[service])

    body, code = http_request("GET", url, headers=hdrs)

    return process_primary_response(service, body, code, response_format)


def process_primary_response(service: str, body: str, code: int, response_format: str) -> str:
    # Check HTTP error first
    status = status_from_http_code(code)
    if status:
        return status

    if not body or "<html" in body.lower():
        return STATUS_NA

    if response_format == "plain":
        return body.strip()

    data = safe_json_parse(body)
    if data is None:
        log("ERROR", f"Invalid JSON from {service}: {body[:200]}")
        return STATUS_NA

    path = JQ_FILTERS.get(service)
    if path is None:
        return STATUS_NA

    value = json_extract(data, path)
    if value is None or value == "null" or value == "":
        return STATUS_NA

    return str(value)


# ─── Primary Custom Handlers ────────────────────────────────────────────────────

def lookup_cloudflare_primary() -> str:
    """Parse loc=XX from cloudflare cdn-cgi/trace plain text."""
    body, code = http_request("GET", "https://www.cloudflare.com/cdn-cgi/trace")
    status = status_from_http_code(code)
    if status:
        return status
    for line in body.splitlines():
        if line.startswith("loc="):
            return line[4:].strip()
    return STATUS_NA


def lookup_iplocation_com(ip: str) -> str:
    body, code = http_request(
        "POST", "https://iplocation.com",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data=f"ip={ip}".encode("utf-8"),
        user_agent=USER_AGENT,
    )
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        return data.get("country_code", STATUS_NA) or STATUS_NA
    return STATUS_NA


def lookup_2ip() -> str:
    body, code = http_request("GET", "https://api.2ip.io")
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        return data.get("code", STATUS_NA) or STATUS_NA
    return STATUS_NA


# ─── Custom Service Lookups ─────────────────────────────────────────────────────

def lookup_google() -> str:
    body, code = http_request("GET", "https://www.google.com", user_agent=USER_AGENT)
    status = status_from_http_code(code)
    if status:
        return status
    # Primary: MgUcDb field
    m = re.search(r'"MgUcDb":"([^"]*)"', body)
    if m:
        return m.group(1)
    # Fallback: locale pattern like "en_RU" or "en-RU"
    m = re.search(r'"[a-z]{2}_([A-Z]{2})"', body)
    if m:
        return m.group(1)
    m = re.search(r'"[a-z]{2}-([A-Z]{2})"', body)
    if m:
        return m.group(1)
    return STATUS_NA


def lookup_youtube() -> str:
    body, code = http_request("GET", "https://www.youtube.com", user_agent=USER_AGENT)
    status = status_from_http_code(code)
    if status:
        return status
    m = re.search(r'"countryCode":"(\w+)"', body)
    if m and len(m.group(1)) <= 3:
        return m.group(1)
    return STATUS_NA


def lookup_twitch() -> str:
    body, code = http_request(
        "POST", "https://gql.twitch.tv/gql",
        headers={"Client-Id": TWITCH_CLIENT_ID},
        json_body='[{"operationName":"VerifyEmail_CurrentUser","variables":{},"extensions":{"persistedQuery":{"version":1,"sha256Hash":"f9e7dcdf7e99c314c82d8f7f725fab5f99d1df3d7359b53c9ae122deec590198"}}}]',
    )
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data:
        try:
            return data[0]["data"]["requestInfo"]["countryCode"]
        except (IndexError, KeyError, TypeError):
            pass
    return STATUS_NA


def lookup_chatgpt() -> str:
    body, code = http_request(
        "POST", "https://ab.chatgpt.com/v1/initialize",
        headers={"Statsig-Api-Key": CHATGPT_STATSIG_API_KEY},
    )
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        df = data.get("derived_fields", {})
        return df.get("country", STATUS_NA) or STATUS_NA
    return STATUS_NA


def lookup_netflix() -> str:
    url = f"https://api.fast.com/netflix/speedtest/v2?https=true&token={NETFLIX_API_KEY}&urlCount=1"
    body, code = http_request("GET", url)
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        client = data.get("client", {})
        location = client.get("location", {})
        return location.get("country", STATUS_NA) or STATUS_NA
    return body.strip() if body.strip() else STATUS_NA


def lookup_spotify() -> str:
    body, code = http_request("GET", "https://accounts.spotify.com/status")
    status = status_from_http_code(code)
    if status:
        return status
    m = re.search(r'"geoLocationCountryCode":"([^"]+)"', body)
    return m.group(1) if m else STATUS_NA


def lookup_reddit() -> str:
    basic_token = f"Basic {REDDIT_BASIC_ACCESS_TOKEN}"
    ua = "Reddit/Version 2025.29.0/Build 2529021/Android 13"

    body, code = http_request(
        "POST", "https://www.reddit.com/auth/v2/oauth/access-token/loid",
        headers={"Authorization": basic_token},
        json_body='{"scopes":["email"]}',
        user_agent=ua,
    )

    data = safe_json_parse(body)
    if not data or not isinstance(data, dict):
        return STATUS_NA

    access_token = data.get("access_token", "")
    if not access_token:
        return STATUS_NA

    body2, code2 = http_request(
        "POST", "https://gql-fed.reddit.com",
        headers={"Authorization": f"Bearer {access_token}"},
        json_body='{"operationName":"UserLocation","variables":{},"extensions":{"persistedQuery":{"version":1,"sha256Hash":"f07de258c54537e24d7856080f662c1b1268210251e5789c8c08f20d76cc8ab2"}}}',
        user_agent=ua,
    )

    data2 = safe_json_parse(body2)
    if data2 and isinstance(data2, dict):
        try:
            return data2["data"]["userLocation"]["countryCode"]
        except (KeyError, TypeError):
            pass
    return STATUS_NA



def lookup_reddit_guest_access() -> str:
    body, code = http_request("GET", "https://www.reddit.com", user_agent=USER_AGENT)
    if code == 403 or status_from_http_code(code) == STATUS_DENIED:
        return "No"
    return "Yes" if body else STATUS_NA


def lookup_youtube_premium() -> str:
    body, code = http_request(
        "GET", "https://www.youtube.com/premium",
        headers={
            "Cookie": f"SOCS={YOUTUBE_SOCS_COOKIE}",
            "Accept-Language": "en-US,en;q=0.9",
        },
        user_agent=USER_AGENT,
    )
    if not body:
        return STATUS_NA
    if re.search(r"youtube premium is not available in your country", body, re.IGNORECASE):
        return "No"
    return "Yes"


def lookup_google_search_captcha() -> str:
    body, code = http_request(
        "GET", "https://www.google.com/search?q=cats",
        headers={"Accept-Language": "en-US,en;q=0.9"},
        user_agent=USER_AGENT,
    )
    if not body:
        return STATUS_NA
    if re.search(r"unusual traffic from|is blocked|unaddressed abuse", body, re.IGNORECASE):
        return "Yes"
    return "No"


def lookup_spotify_signup() -> str:
    url = f"https://spclient.wg.spotify.com/signup/public/v1/account/?validate=1&key={SPOTIFY_API_KEY}"
    body, code = http_request(
        "GET", url,
        headers={"X-Client-Id": SPOTIFY_CLIENT_ID},
    )
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        s = str(data.get("status", ""))
        launched = data.get("is_country_launched", True)
        if s in ("120", "320") or launched is False:
            return "No"
        return "Yes"
    return STATUS_NA


def lookup_steam() -> str:
    """Use http.client directly to capture Set-Cookie before redirects."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection("store.steampowered.com", timeout=state.timeout, context=ctx)
        conn.request("GET", "/", headers={"User-Agent": USER_AGENT})
        resp = conn.getresponse()
        # Check all Set-Cookie headers
        for header_name, header_val in resp.getheaders():
            if header_name.lower() == "set-cookie":
                m = re.search(r'steamCountry=([^%;]+)', header_val)
                if m:
                    conn.close()
                    return m.group(1)
        conn.close()
    except Exception as e:
        log("WARNING", f"Steam lookup failed: {e}")
    return STATUS_NA


def lookup_youtube_music() -> str:
    body, code = http_request(
        "GET", "https://music.youtube.com/",
        headers={
            "Cookie": f"SOCS={YOUTUBE_SOCS_COOKIE}",
            "Accept-Language": "en-US,en;q=0.9",
        },
        user_agent=USER_AGENT,
    )
    if not body:
        return STATUS_NA
    if re.search(r"YouTube Music is not available in your area", body, re.IGNORECASE):
        return "No"
    return "Yes"


def lookup_deezer() -> str:
    body, code = http_request("GET", "https://www.deezer.com/en/offers")
    status = status_from_http_code(code)
    if status:
        return status
    m = re.search(r"'country':\s*'([^']+)'", body)
    return m.group(1) if m else STATUS_NA


def lookup_amazon_prime() -> str:
    body, code = http_request(
        "GET", "https://www.primevideo.com",
        user_agent=USER_AGENT,
    )
    status = status_from_http_code(code)
    if status:
        return status
    m = re.search(r'"currentTerritory":"([^"]+)"', body)
    if m:
        return m.group(1)[:2]
    return STATUS_NA


def lookup_bing() -> str:
    body, code = http_request(
        "GET", "https://www.bing.com/search?q=cats",
        user_agent=USER_AGENT,
    )
    status = status_from_http_code(code)
    if status:
        return status
    # Check for CN redirect
    if "cn.bing.com" in body:
        return "CN"
    m = re.search(r'Region\s*:\s*"([^"]+)"', body)
    if m:
        region = m.group(1)[:2]
        if region == "WW":
            # Fallback to login.live.com
            return lookup_bing_fallback()
        return region
    return STATUS_NA


def lookup_bing_fallback() -> str:
    body, code = http_request("GET", "https://login.live.com", user_agent=USER_AGENT)
    m = re.search(r'"sRequestCountry":"([^"]*)"', body)
    return m.group(1) if m else STATUS_NA


def lookup_apple() -> str:
    body, code = http_request("GET", "https://gspe1-ssl.ls.apple.com/pep/gcc")
    status = status_from_http_code(code)
    if status:
        return status
    return body.strip() if body.strip() else STATUS_NA





def lookup_tiktok() -> str:
    body, code = http_request(
        "GET", "https://www.tiktok.com/api/v1/web-cookie-privacy/config?appId=1988",
        user_agent=USER_AGENT,
    )
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        try:
            return data["body"]["appProps"]["region"]
        except (KeyError, TypeError):
            pass
    return STATUS_NA





def lookup_youtube_cdn() -> str:
    body, code = http_request(
        "GET", "https://redirector.googlevideo.com/report_mapping?di=no",
        user_agent=USER_AGENT,
    )
    status = status_from_http_code(code)
    if status:
        return status
    if not body.strip():
        return STATUS_NA
    # Parse: extract IATA from 3rd field, split by '-', take 2nd part, first 3 chars
    for line in body.strip().splitlines():
        parts = line.split()
        if len(parts) >= 3:
            subparts = parts[2].split("-")
            if len(subparts) >= 2:
                iata = subparts[1][:3].upper()
                if iata and iata.isalpha():
                    location = get_iata_location(iata)
                    return f"{location} ({iata})" if location else iata
    return STATUS_NA


def lookup_netflix_cdn() -> str:
    url = f"https://api.fast.com/netflix/speedtest/v2?https=true&token={NETFLIX_API_KEY}&urlCount=1"
    body, code = http_request("GET", url)
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        targets = data.get("targets", [])
        if targets:
            loc = targets[0].get("location", {})
            return loc.get("country", STATUS_NA) or STATUS_NA
    return STATUS_NA


def lookup_ookla_speedtest() -> str:
    body, code = http_request("GET", "https://www.speedtest.net/api/js/config-sdk")
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        loc = data.get("location", {})
        return loc.get("countryCode", STATUS_NA) or STATUS_NA
    return STATUS_NA


def lookup_jetbrains() -> str:
    body, code = http_request("GET", "https://data.services.jetbrains.com/geo")
    status = status_from_http_code(code)
    if status:
        return status
    data = safe_json_parse(body)
    if data and isinstance(data, dict):
        return data.get("code", STATUS_NA) or STATUS_NA
    return STATUS_NA


def lookup_playstation() -> str:
    """Use http.client to get Set-Cookie headers."""
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection("www.playstation.com", timeout=state.timeout, context=ctx)
        conn.request("HEAD", "/", headers={"User-Agent": USER_AGENT})
        resp = conn.getresponse()
        for header_name, header_val in resp.getheaders():
            if header_name.lower() == "set-cookie":
                m = re.search(r'country=([A-Z]{2})', header_val)
                if m:
                    conn.close()
                    return m.group(1)
        conn.close()
    except Exception as e:
        log("WARNING", f"PlayStation lookup failed: {e}")
    return STATUS_NA





# ─── Service Handler Map ───────────────────────────────────────────────────────

CUSTOM_HANDLERS = {
    "GOOGLE": lookup_google,
    "GOOGLE_SEARCH_CAPTCHA": lookup_google_search_captcha,
    "YOUTUBE": lookup_youtube,
    "YOUTUBE_PREMIUM": lookup_youtube_premium,
    "YOUTUBE_MUSIC": lookup_youtube_music,
    "TWITCH": lookup_twitch,
    "CHATGPT": lookup_chatgpt,
    "NETFLIX": lookup_netflix,
    "SPOTIFY": lookup_spotify,
    "SPOTIFY_SIGNUP": lookup_spotify_signup,
    "DEEZER": lookup_deezer,
    "REDDIT": lookup_reddit,
    "REDDIT_GUEST_ACCESS": lookup_reddit_guest_access,
    "AMAZON_PRIME": lookup_amazon_prime,
    "APPLE": lookup_apple,
    "STEAM": lookup_steam,
    "PLAYSTATION": lookup_playstation,
    "TIKTOK": lookup_tiktok,
    "OOKLA_SPEEDTEST": lookup_ookla_speedtest,
    "JETBRAINS": lookup_jetbrains,
    "BING": lookup_bing,
}

CDN_HANDLERS = {
    "YOUTUBE_CDN": lookup_youtube_cdn,
    "NETFLIX_CDN": lookup_netflix_cdn,
}


# ─── Service Running ───────────────────────────────────────────────────────────

def run_primary_services():
    for service in PRIMARY_SERVICES_ORDER:
        if service in EXCLUDED_SERVICES:
            log("INFO", f"Skipping {service}")
            continue

        cfg = PRIMARY_SERVICES.get(service, "")
        display_name = cfg.split("|")[0] if cfg else service
        spinner.update(display_name)

        ipv4_result = ""
        ipv6_result = ""

        if service in PRIMARY_CUSTOM_HANDLERS:
            # Services with custom handler functions
            if service == "IPLOCATION_COM":
                if can_use_ipv4():
                    ipv4_result = lookup_iplocation_com(state.external_ipv4)
                if can_use_ipv6():
                    ipv6_result = lookup_iplocation_com(state.external_ipv6)
            elif service == "CLOUDFLARE":
                if can_use_ipv4():
                    with force_ip_version(4):
                        ipv4_result = lookup_cloudflare_primary()
                if can_use_ipv6():
                    with force_ip_version(6):
                        ipv6_result = lookup_cloudflare_primary()
            elif service == "2IP":
                if can_use_ipv4():
                    with force_ip_version(4):
                        ipv4_result = lookup_2ip()
                if can_use_ipv6():
                    with force_ip_version(6):
                        ipv6_result = lookup_2ip()
        else:
            if can_use_ipv4():
                log("INFO", f"Checking {display_name} via IPv4")
                ipv4_result = probe_primary_service(service, state.external_ipv4)
            if can_use_ipv6():
                log("INFO", f"Checking {display_name} via IPv6")
                ipv6_result = probe_primary_service(service, state.external_ipv6)

        state.results_primary.append((display_name, ipv4_result, ipv6_result))


def _run_handler_group(services_order, services_map, handlers_map, results_list):
    """Generic runner for custom and CDN service groups."""
    for service in services_order:
        if service in EXCLUDED_SERVICES:
            log("INFO", f"Skipping {service}")
            continue

        display_name = services_map.get(service, service)
        spinner.update(display_name)
        handler = handlers_map.get(service)

        if not handler:
            log("WARNING", f"No handler for {service}")
            continue

        ipv4_result = ""
        ipv6_result = ""

        if can_use_ipv4():
            log("INFO", f"Checking {display_name} via IPv4")
            try:
                with force_ip_version(4):
                    ipv4_result = handler()
            except Exception as e:
                log("ERROR", f"Error checking {display_name} (IPv4): {e}")
                ipv4_result = STATUS_NA

        if can_use_ipv6():
            log("INFO", f"Checking {display_name} via IPv6")
            try:
                with force_ip_version(6):
                    ipv6_result = handler()
            except Exception as e:
                log("ERROR", f"Error checking {display_name} (IPv6): {e}")
                ipv6_result = STATUS_NA

        results_list.append((display_name, ipv4_result, ipv6_result))


def run_custom_services():
    _run_handler_group(CUSTOM_SERVICES_ORDER, CUSTOM_SERVICES, CUSTOM_HANDLERS, state.results_custom)


def run_cdn_services():
    _run_handler_group(CDN_SERVICES_ORDER, CDN_SERVICES, CDN_HANDLERS, state.results_cdn)


# ─── Output ─────────────────────────────────────────────────────────────────────

def build_json_output() -> dict:
    def group_to_list(results):
        out = []
        for service, v4, v6 in results:
            entry = {"service": service}
            entry["ipv4"] = v4 if v4 else None
            entry["ipv6"] = v6 if v6 else None
            out.append(entry)
        return out

    return {
        "version": 1,
        "ipv4": state.external_ipv4 or None,
        "ipv6": state.external_ipv6 or None,
        "results": {
            "primary": group_to_list(state.results_primary),
            "custom": group_to_list(state.results_custom),
            "cdn": group_to_list(state.results_cdn),
        }
    }


def print_header():
    print(f"{color('URL', 'Made with ')}{color('HEART', '<3')}{color('URL', ' by deathnoragami')}")
    print(f"{color('URL', SCRIPT_URL)}\n")

    if state.external_ipv4:
        reg = get_registered_country(4)
        reg_str = f", registered in {bold(reg)}" if reg else ""
        print(f"{color('HEADER', 'IPv4')}: {bold(mask_ipv4(state.external_ipv4))}{reg_str}")

    if state.external_ipv6:
        reg = get_registered_country(6)
        reg_str = f", registered in {bold(reg)}" if reg else ""
        print(f"{color('HEADER', 'IPv6')}: {bold(mask_ipv6(state.external_ipv6))}{reg_str}")

    if state.asn:
        print(f"{color('HEADER', 'ASN')}: {bold(f'AS{state.asn} {state.asn_name}')}")
    print()


def print_table_group(title: str, results: list):
    if not results:
        return

    show_v4 = can_use_ipv4()
    show_v6 = can_use_ipv6()

    print(f"{color('HEADER', title)}\n")

    # Calculate column widths (strip ANSI for measurement)
    ansi_re = re.compile(r'\033\[[0-9;]*m')

    def visible_len(s: str) -> int:
        return len(ansi_re.sub('', s))

    # Build rows
    header_cols = [color("TABLE_HEADER", "Service")]
    if show_v4:
        header_cols.append(color("TABLE_HEADER", "IPv4"))
    if show_v6:
        header_cols.append(color("TABLE_HEADER", "IPv6"))

    rows = []
    for service, v4, v6 in results:
        row = [color("SERVICE", service)]
        if show_v4:
            val = v4 if v4 else "N/A"
            row.append(format_value(val))
        if show_v6:
            val = v6 if v6 else "N/A"
            row.append(format_value(val))
        rows.append(row)

    # Determine column widths
    all_rows = [header_cols] + rows
    num_cols = len(header_cols)
    widths = [0] * num_cols

    for row in all_rows:
        for i, cell in enumerate(row):
            w = visible_len(cell)
            if w > widths[i]:
                widths[i] = w

    # Print with padding
    for row in all_rows:
        parts = []
        for i, cell in enumerate(row):
            pad = widths[i] - visible_len(cell)
            parts.append(cell + " " * pad)
        print("  ".join(parts))

    print()


def print_results():
    if state.json_output:
        result = build_json_output()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    print_header()

    groups = state.groups_to_show

    if groups == "primary":
        print_table_group("GeoIP services", state.results_primary)
    elif groups == "custom":
        print_table_group("Popular services", state.results_custom)
    elif groups == "cdn":
        print_table_group("CDN services", state.results_cdn)
    else:
        print_table_group("Popular services", state.results_custom)
        print_table_group("CDN services", state.results_cdn)
        print_table_group("GeoIP services", state.results_primary)


# ─── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        prog=SCRIPT_NAME,
        description="IPRegion — determines your IP geolocation using various GeoIP services and popular websites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python {SCRIPT_NAME}                       # Check all services
  python {SCRIPT_NAME} -g primary            # Check only GeoIP services
  python {SCRIPT_NAME} -g custom             # Check only popular websites
  python {SCRIPT_NAME} -g cdn                # Check only CDN endpoints
  python {SCRIPT_NAME} -j                    # Output result as JSON
  python {SCRIPT_NAME} -v                    # Enable verbose logging
  python {SCRIPT_NAME} -p socks5:127.0.0.1:1080  # Use SOCKS5 proxy
  python {SCRIPT_NAME} -p http:127.0.0.1:8080    # Use HTTP proxy
""",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("-j", "--json", action="store_true", dest="json_output", help="Output results in JSON format")
    parser.add_argument(
        "-g", "--group",
        choices=["primary", "custom", "cdn", "all"],
        default="all",
        help="Run only one group (default: all)",
    )
    parser.add_argument("-t", "--timeout", type=int, default=5, help="Request timeout in seconds (default: 5)")
    parser.add_argument(
        "-p", "--proxy",
        help="Proxy address. Formats: socks5:host:port or http:host:port",
    )

    return parser.parse_args()


# ─── Main ───────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    state.verbose = args.verbose
    state.json_output = args.json_output
    state.groups_to_show = args.group
    state.timeout = args.timeout

    # Handle proxy
    if args.proxy:
        proxy_str = args.proxy
        if proxy_str.startswith("socks5:"):
            state.proxy_type = "socks5"
            state.proxy_addr = proxy_str[7:]  # Remove "socks5:" prefix
            ensure_socks5_support()
            setup_socks5_proxy(state.proxy_addr)
            log("INFO", f"Using SOCKS5 proxy: {state.proxy_addr}")
        elif proxy_str.startswith("http:"):
            state.proxy_type = "http"
            state.proxy_addr = proxy_str[5:]  # Remove "http:" prefix
            log("INFO", f"Using HTTP proxy: {state.proxy_addr}")
        else:
            # Default: try as SOCKS5 for backward compatibility
            state.proxy_type = "socks5"
            state.proxy_addr = proxy_str
            ensure_socks5_support()
            setup_socks5_proxy(state.proxy_addr)
            log("INFO", f"Using SOCKS5 proxy: {state.proxy_addr}")

    # Start spinner
    spinner.start()

    try:
        # Check IP support
        if not state.ipv6_only:
            state.ipv4_supported = check_ip_support(4)
        if not state.ipv4_only:
            state.ipv6_supported = check_ip_support(6)

        # Discover external IPs
        discover_external_ips()

        # Get ASN
        get_asn()

        # Run services
        groups = state.groups_to_show
        if groups in ("all", "primary"):
            run_primary_services()
        if groups in ("all", "custom"):
            run_custom_services()
        if groups in ("all", "cdn"):
            run_cdn_services()

    except KeyboardInterrupt:
        spinner.stop()
        print(f"\n{color('WARN', 'Interrupted by user')}")
        sys.exit(130)
    finally:
        spinner.stop()

    # Print results
    print_results()


if __name__ == "__main__":
    main()
