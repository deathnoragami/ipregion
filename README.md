<div align="center">

# 🌎 IPRegion

**Multi-source IP geolocation tester**
Check how streaming, GeoIP, and CDN services detect your location.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![No Dependencies](https://img.shields.io/badge/Dependencies-None*-orange?style=for-the-badge)](#requirements)

**[English](#-overview)** · **[Русский](#-обзор)**

</div>

---

## 📖 Overview

Uses **only standard Python libraries** — no `pip install` required.

### 🚀 Run instantly (one command)

**Linux / macOS:**
```bash
curl -sL https://raw.githubusercontent.com/deathnoragami/ipregion/main/ipregion.py | python3 -
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/deathnoragami/ipregion/main/ipregion.py | python -
```

**With arguments:**
```bash
curl -sL https://raw.githubusercontent.com/deathnoragami/ipregion/main/ipregion.py | python3 - -g primary -j
```

### ✨ Key Features

- 🔍 **40+ services** — GeoIP APIs, streaming platforms, CDN endpoints
- 📦 **Zero dependencies** — works on any Python 3.10+ out of the box
- 🌐 **IPv4 & IPv6** — detects and tests both protocols automatically
- 🧦 **SOCKS5 proxy** — auto-installs [PySocks](https://pypi.org/project/PySocks/) if needed
- 🔌 **HTTP proxy** — built-in support via `urllib`
- 📊 **JSON output** — machine-readable results with `-j`
- 🎨 **Colored tables** — beautiful terminal output with ANSI colors

---

### � Install (optional)

```bash
git clone https://github.com/deathnoragami/ipregion.git
cd ipregion
python ipregion.py
```

### 📋 Usage

```bash
python ipregion.py                             # Check all services
python ipregion.py -g primary                  # GeoIP services only
python ipregion.py -g custom                   # Popular websites only
python ipregion.py -g cdn                      # CDN endpoints only
python ipregion.py -j                          # JSON output
python ipregion.py -v                          # Verbose logging
python ipregion.py -t 10                       # Timeout 10 seconds
python ipregion.py -p socks5:127.0.0.1:1080    # SOCKS5 proxy
python ipregion.py -p http:127.0.0.1:8080      # HTTP proxy
```

### ⚙️ Options

| Flag | Description |
|------|-------------|
| `-h, --help` | Show help message |
| `-v, --verbose` | Enable verbose logging |
| `-j, --json` | Output results as JSON |
| `-g, --group` | Service group: `primary`, `custom`, `cdn`, or `all` |
| `-t, --timeout` | Request timeout in seconds (default: 5) |
| `-p, --proxy` | Proxy: `socks5:host:port`, `http:host:port`, or `host:port` |

### 🔌 Services

<details>
<summary><b>GeoIP Services (16)</b></summary>

MaxMind · RIPE · ipinfo.io · Cloudflare · ipregistry · ipapi.co · iplocation.com · country.is · geoapify.com · geojs.io · ipapi.is · ipbase.com · ipquery.io · ipwho.is · ip-api.com · 2ip.io

</details>

<details>
<summary><b>Popular Services (21)</b></summary>

Google · YouTube · YouTube Premium · YouTube Music · Twitch · ChatGPT · Netflix · Spotify · Spotify Signup · Deezer · Reddit · Reddit Guest Access · Amazon Prime · Apple · Steam · PlayStation · TikTok · Ookla Speedtest · JetBrains · Microsoft (Bing) · Google Search Captcha

</details>

<details>
<summary><b>CDN Services (2)</b></summary>

YouTube CDN · Netflix CDN

</details>

### 📋 Requirements

- **Python 3.10+**
- No additional packages required
- `PySocks` — auto-installed **only** if SOCKS5 proxy is used

---

## � Обзор

Использует **только стандартные библиотеки Python** — установка через `pip` не требуется.

### 🚀 Запуск одной командой

**Linux / macOS:**
```bash
curl -sL https://raw.githubusercontent.com/deathnoragami/ipregion/main/ipregion.py | python3 -
```

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/deathnoragami/ipregion/main/ipregion.py | python -
```

**С аргументами:**
```bash
curl -sL https://raw.githubusercontent.com/deathnoragami/ipregion/main/ipregion.py | python3 - -g primary -j
```

### ✨ Ключевые возможности

- 🔍 **40+ сервисов** — GeoIP API, стриминговые платформы, CDN
- 📦 **Без зависимостей** — работает на любом Python 3.10+
- 🌐 **IPv4 и IPv6** — автоматически определяет и тестирует оба протокола
- 🧦 **SOCKS5 прокси** — автоустановка [PySocks](https://pypi.org/project/PySocks/) при необходимости
- 🔌 **HTTP прокси** — встроенная поддержка через `urllib`
- 📊 **JSON вывод** — машиночитаемые результаты с `-j`
- 🎨 **Цветные таблицы** — красивый вывод с ANSI-цветами

### 📥 Установка (опционально)

```bash
git clone https://github.com/deathnoragami/ipregion.git
cd ipregion
python ipregion.py
```

### 📋 Использование

```bash
python ipregion.py                             # Проверить все сервисы
python ipregion.py -g primary                  # Только GeoIP
python ipregion.py -g custom                   # Только популярные сайты
python ipregion.py -g cdn                      # Только CDN
python ipregion.py -j                          # Вывод в JSON
python ipregion.py -v                          # Подробный лог
python ipregion.py -t 10                       # Таймаут 10 секунд
python ipregion.py -p socks5:127.0.0.1:1080    # SOCKS5 прокси
python ipregion.py -p http:127.0.0.1:8080      # HTTP прокси
```

### ⚙️ Параметры

| Флаг | Описание |
|------|----------|
| `-h, --help` | Справка |
| `-v, --verbose` | Подробное логирование |
| `-j, --json` | Вывод в формате JSON |
| `-g, --group` | Группа: `primary`, `custom`, `cdn` или `all` |
| `-t, --timeout` | Таймаут запроса в секундах (по умолчанию: 5) |
| `-p, --proxy` | Прокси: `socks5:host:port`, `http:host:port` или `host:port` |

### 📋 Требования

- **Python 3.10+**
- Дополнительные пакеты не нужны
- `PySocks` — устанавливается автоматически **только** при использовании SOCKS5
