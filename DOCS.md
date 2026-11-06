# 🍻 Cheers Dating — Full Documentation

Production-ready Telegram dating bot for adults 18+ in Ethiopia. Built with Python 3.11+, aiogram 3, SQLAlchemy 2, PostgreSQL/SQLite, Alembic, Docker, and deployable to Vercel + Neon.

---

## Table of Contents

1. [Overview](#overview)
2. [Feature List](#feature-list)
3. [User Journey — Registration Flow](#user-journey--registration-flow)
4. [User Journey — Discovery & Matching](#user-journey--discovery--matching)
5. [User Journey — Messaging](#user-journey--messaging)
6. [User Journey — Profile Lifecycle](#user-journey--profile-lifecycle)
7. [Commands Reference](#commands-reference)
8. [Configuration Reference](#configuration-reference)
9. [Architecture](#architecture)
10. [Database Schema](#database-schema)
11. [Alembic Migrations](#alembic-migrations)
12. [Premium System](#premium-system)
13. [Admin Dashboard](#admin-dashboard)
14. [Security & Privacy](#security--privacy)
15. [Local Development on Windows](#local-development-on-windows)
16. [Docker Deployment](#docker-deployment)
17. [Vercel + Neon Deployment](#vercel--neon-deployment)
18. [Testing](#testing)
19. [Troubleshooting](#troubleshooting)
20. [Production Checklist](#production-checklist)

---

## Overview

Cheers Dating is a privacy-first Telegram dating bot for adults 18+ in Ethiopia. It keeps Telegram identities (usernames, numeric IDs) hidden from other members. Profiles are shown using internal database IDs only. Conversations unlock only after a mutual like. Every member can report, block, pause, or delete their account.

**Tech stack:**
- Python 3.11+ (3.12 recommended)
- aiogram 3.x (Telegram Bot API framework)
- SQLAlchemy 2.x (async ORM)
- Alembic (database migrations)
- SQLite (local dev / tests)
- PostgreSQL + asyncpg (production / Neon / Docker)
- FastAPI + Vercel Functions (serverless webhook hosting)
- Pytest (67 tests), ruff (lint)

---

## Feature List

### Onboarding & Profiles
- Mandatory 18+ confirmation + date-of-birth validation
- Registration collects: name, DOB, gender, religion (Orthodox / Muslim / Catholic / Protestant), dating preference (men / women), city, bio, interests (up to 8), relationship intention, up to 3 photos
- Profile preview + confirmation before going live
- Edit profile fields and photos
- Pause / reactivate profile
- Permanent account deletion

### Discovery & Matching
- Card-based discovery with Like / Pass
- No self-discovery, no repeated profiles, no already-liked/passed profiles
- Mutual likes create a match and notify both users
- Filters: age range, gender, religion, city, recently-active-only
- Auto opposite-sex matching by default (men see women, women see men)
- Daily discovery limits (configurable free vs premium)
- "Who liked you" list (premium members see everyone who liked them)
- Total matches and today's matches displayed on matches screen (promotional stat)

### Private Messaging
- Text and photo messages relayed only between matched members
- Telegram usernames, IDs, phone numbers, emails, and links blocked by default
- Unmatch, block, and report flows
- Reports capture reason + optional details for moderators

### Administration
- Dashboard: registrations, active users, matches, open reports, bans, premium counts
- Report queue: ban, resolve, dismiss actions
- User search by database ID, Telegram ID, name, username, or city
- Ban / unban, premium grant / revoke
- Broadcast to all active users (durable, resumable jobs)
- Admin audit trail (append-only)
- Admin access restricted to `ADMIN_IDS` Telegram IDs (defence in depth)

### Platform
- Async SQLAlchemy, SQLite local, PostgreSQL production
- Alembic migrations as schema source of truth
- Per-user sliding-window anti-spam throttling
- Centralised error handler
- Dockerfile + docker-compose.yml
- Vercel serverless webhook deployment

---

## User Journey — Registration Flow

The bot enforces a strict 18+ onboarding. Users cannot access dating features until registration is complete.

### Step 1 — Age Confirmation
User sends `/start`. Bot replies with privacy notice and a "✅ I'm 18 — continue" button.

### Step 2 — First Name
User sends their first name (2–32 characters).

### Step 3 — Date of Birth
User sends DOB as `DD/MM/YYYY` (e.g. `14/02/1996`).
- Must be 18 or older
- Future dates are rejected
- Exact birth date is never shown to others — only age

### Step 4 — Gender
Inline keyboard: 👨 Man / 👩 Woman

### Step 5 — Religion
Inline keyboard: 🇪🇹 Orthodox / 🕌 Muslim / ⛪ Catholic / ✝️ Protestant

### Step 6 — City
Inline keyboard of Ethiopian cities (Addis Ababa, Adama, Bahir Dar, Hawassa, Gondar, Mekelle, Dire Dawa, Jimma, Bishoftu, Jijiga, Shashamane, Arba Minch, Harar, Dessie, Nekemte) plus "🌍 Other city" for custom entry.

### Step 7 — Bio
Free text (10–500 characters). No phone numbers, usernames, or links. Can be skipped.

### Step 8 — Interests
Inline checkboxes, up to 8 selections from: Coffee, Music, Travel, Movies, Books, Fitness, Cooking, Nature, Football, Art, Tech, Dancing.

### Step 9 — Intention
Inline keyboard: Serious relationship / Long-term partner / New friendships / Casual dating / Marriage-minded / Still figuring it out.

### Step 10 — Photos
User sends up to 3 photos, one at a time. First photo is the main photo.

### Step 11 — Confirm
Preview screen shows: name, age, city, gender, religion, intention, bio, interests, photo count. User taps "🎉 Create my profile" to go live.

### Back Button
Every step has a "⬅️ Back" button. Going back clears forward-entered data but preserves previously entered values. Users can fix mistakes without starting over.

---

## User Journey — Discovery & Matching

### Discovery Card
User sends `/discover` or taps "🔍 Discover". Bot shows one profile card at a time:
- Name, age, city, gender, religion, intention
- Bio and interests
- Main photo (if available)
- Footer: remaining daily discoveries

### Actions on Each Card
- **❤️ Like** — Records a like. If the target already liked the user back, a mutual match is created and both users are notified ("💥 It's a match!").
- **👎 Pass** — Records a pass. The profile won't be shown again.
- **🚩 Report** — Opens report flow (reason + optional details).
- **🚫 Block** — Blocks the user. They won't appear in discovery and can't interact.
- **⚙️ Filters** — Opens discovery filters menu.
- **🏠 Menu** — Returns to main menu.

### Filters (/settings → ⚙️ Filters)
- **Age range** — Presets: 18–25, 18–35, 25–35, 25–45, 35–50, 40–65, or Any (18–99)
- **Gender** — Man / Woman / Any (default: opposite sex based on viewer's gender)
- **Religion** — Orthodox / Muslim / Catholic / Protestant / Any
- **City** — Select from Ethiopian cities or "Any city"
- **Recently active only** — Premium feature; shows users active in the last 7 days

### Discovery Rules
- No self-discovery (can't see your own profile)
- No repeated profiles (each profile shown once)
- No already-liked or already-passed profiles
- No profiles of blocked users or users who blocked you
- No profiles of users with open/reviewing reports against them from you
- Reciprocal preference: a man only sees women who are interested in men or everyone; a woman only sees men interested in women or everyone
- Daily discovery limit applies (30 free / 300 premium)

### Matches
User sends `/matches` or taps "💬 Matches". Shows:
- Number of mutual matches
- Total matches on the platform (promotional stat)
- Today's matches count (promotional stat)
- Paginated list of matches (8 per page)
- Tap a match to view profile card or open chat

### Likes Received (/likes)
- Shows count of people who liked the user
- Free users see count only; premium users see full profiles and can like back instantly
- Like back creates an immediate match

---

## User Journey — Messaging

### Opening a Chat
From a match card or the matches list, user taps "💬 Say hello" or "💬 Matches". Bot opens a private chat relay:
- Shows partner's name
- Instructs user to send text or photo
- Warns that contact details and links are blocked for safety
- Shows "🚪 Leave chat" button

### During Chat
- User sends text (up to 2,000 characters) or photo
- Bot relays the message to the partner privately
- Partner's Telegram ID, username, phone number, and email are never revealed
- Messages are marked as read when viewed
- User taps "🚪 Leave chat" or `/end` to exit the chat relay
- The match remains in the user's matches list for future chats

### Message Rules
- Only matched members can message each other
- Unmatching ends the chat and removes the match
- Blocking a matched user ends the match and chat
- Reports can be filed against a matched user

---

## User Journey — Profile Lifecycle

### View Profile (/profile)
Shows the user's own profile card: name, age, city, gender, religion, intention, bio, interests, photo count, and photos.

### Edit Profile (/editprofile)
Users can edit:
- First name
- Date of birth (18+ validation)
- Gender
- Religion
- City
- Bio
- Interests
- Intention
- Photos (add, remove, replace up to 3)

### Pause Profile (/pause or Settings → ⏸ Pause profile)
- Hides the profile from discovery
- User won't appear in other people's discovery cards
- Existing matches and chats remain available
- Status shows as "⏸ Paused" in settings and admin panel
- Reactivate anytime via /pause again or "▶️ Resume profile" button

### Delete Account (/deleteaccount)
- Permanently deletes: profile, photos, likes, matches, messages, blocks, reports, daily usage
- Admin audit entries are retained with target user reference cleared (for accountability)
- Cannot be undone
- Requires typing "DELETE" to confirm

---

## Commands Reference

| Command | Description | Who can use |
|---------|-------------|-------------|
| `/start` | Welcome screen and main menu | All users |
| `/help` | Help, safety guidance, and privacy notes | All users |
| `/profile` | View your profile as others see it | Registered users |
| `/editprofile` | Edit profile fields and photos | Registered users |
| `/discover` | Show the next compatible profile | Registered users |
| `/likes` | People who liked you | Registered users |
| `/matches` | Matches and open chats | Registered users |
| `/settings` | Discovery filters, pause/resume, privacy | Registered users |
| `/premium` | Premium status and benefits | Registered users |
| `/report` | Report a matched or recently seen member | Registered users |
| `/block` | Block a member | Registered users |
| `/pause` | Hide your profile from discovery | Registered users |
| `/deleteaccount` | Permanently delete your account and data | Registered users |
| `/admin` | Admin dashboard (staff only) | Admins only (`ADMIN_IDS`) |
| `/cancel` | Cancel the current form or flow | All users |
| `/end` | Leave the active chat relay | In active chat |

---

## Configuration Reference

All settings are read from `.env` (or real environment variables, which take precedence). See `.env.example` for the full list.

| Variable | Default | Purpose |
|----------|---------|---------|
| `BOT_TOKEN` | — | Telegram bot token from @BotFather. **Required.** |
| `DATABASE_URL` | `sqlite+aiosqlite:///./cheers.db` | Async SQLAlchemy URL. PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/db`. |
| `ADMIN_IDS` | empty | Comma-separated numeric Telegram IDs. Required in production. |
| `SUPPORT_CONTACT` | `@cheers_support` | Contact shown in help/premium screens. |
| `ENVIRONMENT` | `development` | `development`, `production`, or `test`. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_FILE` | `logs/cheers.log` | Rotating file log (5 MB × 5). Set empty on Vercel (stdout only). |
| `APP_TIMEZONE` | `Africa/Addis_Ababa` | Timezone for daily limits and admin statistics. |
| `DROP_PENDING_UPDATES` | `false` | Drop queued updates on startup. |
| `AUTO_CREATE_TABLES` | `false` | Create tables without Alembic (development only). |
| `PREMIUM_ENABLED` | `false` | `false` unlocks premium for everyone (launch mode); `true` enforces gating. |
| `FREE_DAILY_DISCOVERIES` | `30` | Daily discovery limit for free members. |
| `PREMIUM_DAILY_DISCOVERIES` | `300` | Daily discovery limit for premium members. |
| `ALLOW_CONTACT_SHARING` | `false` | Allow phone/email/username/link sharing in chat. |
| `RATE_LIMIT_EVENTS` | `12` | Maximum events per user per sliding window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `10` | Sliding-window length in seconds. |
| `POSTGRES_PASSWORD` | — | Used only by Docker Compose for the database container. |
| `SERVERLESS` | `false` | `true` when running on Vercel (enforces DB-backed FSM storage). |
| `VERCEL` | `false` | `true` when running on Vercel. |
| `WEBHOOK_URL` | — | Public https URL of the Vercel deployment. |
| `WEBHOOK_PATH` | `/api/telegram` | Telegram webhook path. |
| `WEBHOOK_SECRET` | — | Telegram `X-Telegram-Bot-Api-Secret-Token` value (A-Za-z0-9_- only). |
| `SETUP_TOKEN` | — | Bearer token to protect `POST /api/setup` (webhook registration). |
| `CRON_SECRET` | — | Bearer token to protect `POST /api/cron/broadcast`. |
| `BROADCAST_INLINE_SECONDS` | `20` | Max seconds a broadcast slice runs inline on Vercel. |

Daily counters reset at midnight in `APP_TIMEZONE`.

---

## Architecture

```text
Telegram update
       │
       ▼
Dispatcher (aiogram)
       │
 outer middlewares:
   database session → user loader/ban gate → throttle → registration gate
       │
       ▼
Routers: admin · common · registration · profile · discovery · matches
         safety · settings · premium · messaging · fallback
       │
       ▼
Services: users · discovery · matches · messages · moderation · premium · admin
       │
       ▼
SQLAlchemy async session → SQLite (dev) / PostgreSQL (production)
```

### Layers

**Handlers** — Translate Telegram events (messages, callback queries) into service calls and render screens with inline keyboards.

**Services** — Contain business rules and are independently testable. Each service handles one domain (users, discovery, matches, messages, moderation, premium, admin, broadcast).

**Middlewares** (per update):
- `DatabaseSessionMiddleware` — Provides an async SQLAlchemy session, commits on success, rolls back on error
- `UserMiddleware` — Loads or creates the user row; blocks banned accounts
- `ThrottlingMiddleware` — Per-user sliding-window anti-spam (12 events / 10 seconds by default)
- `RegistrationGateMiddleware` — Keeps unregistered users in the onboarding flow; admins bypass
- `AdminOnlyMiddleware` (admin router) — Rejects non-admin updates
- `error_handler` — Logs unhandled exceptions; never returns 5xx to Telegram (prevents duplicate actions)

**Models** — Use internal database IDs in callback data. Telegram IDs are never exposed on member-facing screens; only administrators see them.

**FSM Storage** —
- Local polling: in-memory `MemoryStorage`
- Vercel webhook: `DatabaseStorage` backed by PostgreSQL `fsm_states` table (required because serverless functions are ephemeral and concurrent)

**Webhook (Vercel)** — `vercel_app.py` exposes a FastAPI app:
- `POST /api/telegram` — Receives Telegram updates (validated by `X-Telegram-Bot-Api-Secret-Token`)
- `GET /api/health` — Liveness probe with database connectivity check
- `POST /api/setup` — Registers webhook with Telegram (protected by `SETUP_TOKEN`)
- `POST /api/cron/broadcast` — Continues paused broadcast jobs (protected by `CRON_SECRET`)

---

## Database Schema

Two dialects are supported: SQLite (local dev/tests) and PostgreSQL (production/Docker/Neon).

### Tables

| Table | Purpose |
|-------|---------|
| `users` | Core user profile: telegram_id, name, DOB, gender, religion, preference, city, bio, interests, intention, photos, paused/banned/premium flags, timestamps |
| `user_photos` | Up to 3 photos per user with position ordering |
| `user_filters` | Discovery filters per user: min_age, max_age, gender, religion, city, active_recently_only |
| `likes` | Like relationships (from_user → to_user), unique pair, no self-likes |
| `profile_views` | Discovery impressions with action (like/pass) |
| `matches` | Mutual like pairs (ordered user_a < user_b), active/ended status |
| `messages` | Chat messages within matches (text/photo), read status |
| `blocks` | Block relationships (blocker → blocked), unique pair, no self-blocks |
| `reports` | Report records: reporter, reported, reason, status, admin review |
| `admin_actions` | Audit trail: admin ID, action, target user, details, timestamp |
| `daily_usage` | Per-user daily counters: discoveries, likes, messages |
| `fsm_states` | Persistent aiogram FSM state (keyed by StorageKey) for serverless deployment |
| `broadcast_jobs` | Durable admin broadcast jobs with cursor for resumable sending |

### Privacy Notes
- Telegram IDs live only in the database and are never shown to other users
- Member screens and callback data use internal database IDs
- Telegram IDs appear only in admin views
- All user-provided content is stored as-is and escaped at render time

---

## Alembic Migrations

Alembic reads `DATABASE_URL` from the app settings, so the URL is never stored in `alembic.ini`.

### Common Commands

```powershell
# Apply all migrations
alembic upgrade head

# Show current revision
alembic current

# Create a migration after changing models
alembic revision --autogenerate -m "describe change"

# Verify models and migrations agree
alembic check

# Roll back one revision
alembic downgrade -1
```

### Migration History

| Revision | Description |
|----------|-------------|
| `a919b62ec568` | Initial schema: users, photos, filters, likes, views, matches, messages, blocks, reports, admin_actions, daily_usage |
| `ecc98061532c` | Add `fsm_states` (persistent FSM for serverless) and `broadcast_jobs` (durable broadcasts) |
| `4d51760f8cb0` | Add `religion` column to `users` table |
| `e0cc93faec12` | Add `religion` column to `user_filters` table |

### Local Reset
To reset local data: stop the bot, delete `cheers.db`, then run `alembic upgrade head` again. Never delete a production database.

---

## Premium System

### Launch Mode — `PREMIUM_ENABLED=false` (default)
No payment provider is connected yet, so premium features are unlocked for everyone at no cost. This includes the larger discovery limit. Use this while growing the community.

### Paywall Mode — `PREMIUM_ENABLED=true`
Free members get `FREE_DAILY_DISCOVERIES` (30/day). Premium members get:
- `PREMIUM_DAILY_DISCOVERIES` (300/day) discovery limit
- Advanced filters (religion, recently-active-only)
- Full "who liked you" list
- Priority placement in discovery results

Since there is no checkout integration yet, premium access is granted manually by an administrator from the user detail screen in the admin dashboard. Payment integration can be added later without changing the entitlement model.

### Granting Premium
`/admin` → **Users** → search → **Grant 30 days**. Use **Revoke** to end it immediately.

### Entitlement Logic
- `has_premium(user)` returns `True` if `PREMIUM_ENABLED=false`, or if user is premium and not expired
- `daily_discovery_limit(user)` returns premium or free limit accordingly

---

## Admin Dashboard

### Access
Restricted to Telegram IDs in `ADMIN_IDS` (comma-separated). Enforced by router filters and middleware. Unauthorized users receive "This command is for administrators only."

### Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Totals: users, active users, registrations, matches, open reports, bans, premium users |
| **Reports** | Queue of open/reviewing reports with ban, resolve, dismiss actions |
| **Users** | Searchable list by ID, Telegram ID, name, username, or city |
| **User Detail** | Ban/unban, premium grant/revoke, delete user data, view reports |
| **Broadcast** | Send announcement to all active, non-banned users. Durable job with resumable cursor |
| **Audit Log** | Append-only record of bans, unbans, report decisions, premium changes, broadcasts |

### Admin Actions
- **Ban user** — Sets `is_banned=true`; user cannot access dating features; notified via DM
- **Unban user** — Sets `is_banned=false`; user notified via DM
- **Grant premium** — Sets `is_premium=true` with 30-day expiry
- **Revoke premium** — Sets `is_premium=false`, clears expiry
- **Delete user data** — Permanently deletes profile, photos, likes, matches, messages, blocks, reports. Requires typing "DELETE" to confirm. Admin action is logged.
- **Broadcast** — Creates a `broadcast_job` and sends in batches of 100 (~20 msg/sec). On Vercel, runs in inline slices (~20 seconds) and can be resumed via `POST /api/cron/broadcast`

### Audit Trail
All admin actions (ban, unban, report resolve/dismiss, premium grant/revoke, broadcast, delete user) are recorded in `admin_actions` with admin Telegram ID, action type, target user ID, details, and timestamp.

---

## Security & Privacy

- **No hardcoded secrets.** Configuration comes from environment variables; `alembic.ini` contains no URL; `.env` is gitignored.
- **Telegram identity is hidden.** Member screens and callback data use internal database IDs. Telegram IDs appear only in admin views.
- **Matched-only messaging.** Messages are relayed through the bot; members never receive each other's Telegram account details.
- **Contact blocking.** Phone numbers, emails, `@usernames`, and URLs are rejected by default, with `ALLOW_CONTACT_SHARING` as an explicit opt-out.
- **SQL injection protection.** All queries use SQLAlchemy expressions and bound parameters.
- **Rate limiting.** A per-user sliding window rejects floods before handlers run.
- **Admin defence in depth.** Admin routers are filtered by Telegram ID and protected again by middleware; unauthorised callbacks receive an alert.
- **Audit trail.** Bans, unbans, report decisions, premium changes, and broadcasts are recorded in `admin_actions`.
- **Account deletion.** `/deleteaccount` removes the profile, photos, likes, matches, messages, blocks, reports involving the account, and daily usage via database cascades. Admin audit entries are retained with the target user reference cleared, so moderation decisions remain accountable.
- **Age gate.** Users must confirm 18+ and submit a valid adult date of birth. This is self-attestation, not government ID verification; add identity verification if your jurisdiction or risk model requires it.
- **Photos** are stored as Telegram `file_id` references, not downloaded to the server. Telegram hosts the media under its own retention rules.

Report suspected abuse to your configured `SUPPORT_CONTACT`. In an emergency, contact local authorities.

---

## Local Development on Windows

### 1. Requirements
- Python **3.11 or newer** (3.12 recommended)
- A Telegram account and a bot token from [@BotFather](https://t.me/BotFather)

Check Python:
```powershell
python --version
```

### 2. Create and activate a virtual environment
```powershell
cd D:\dating
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Alternatively, call the interpreter directly: `.\.venv\Scripts\python.exe`

### 3. Install dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements.txt` is enough to run the bot; `requirements-dev.txt` adds pytest and ruff.

### 4. Configure the environment
```powershell
Copy-Item .env.example .env
notepad .env
```

At minimum set:
```dotenv
BOT_TOKEN=123456789:your-real-token-from-botfather
ADMIN_IDS=123456789
```

`ADMIN_IDS` accepts comma-separated numeric Telegram IDs. Find yours by sending `/id` to [@userinfobot](https://t.me/userinfobot).

> **Never commit `.env`.** It is already listed in `.gitignore`. If a token was ever pasted into a chat, issue a new token in BotFather with `/revoke` and use the new one.

### 5. Create the database schema
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

This creates `cheers.db` (SQLite) using the default `DATABASE_URL`.

### 6. Run the bot
```powershell
.\.venv\Scripts\python.exe -m app.main
```

You should see `Connected as @your_bot` in the logs. Open the bot in Telegram, send `/start`, and complete registration. As an admin, `/admin` opens the dashboard.

Stop the bot with `Ctrl+C`.

### 7. Everyday commands
```powershell
# Activate the environment
.\.venv\Scripts\Activate.ps1

# Run the bot
python -m app.main

# Apply new migrations
alembic upgrade head

# Run checks
pytest
ruff check app tests
```


## Docker Deployment

Docker Compose runs PostgreSQL and the bot together. Alembic migrations are applied automatically by `docker-entrypoint.sh`, with retries while PostgreSQL starts.

### 1. Prepare the environment
```powershell
Copy-Item .env.example .env
notepad .env
```

Set `BOT_TOKEN`, `ADMIN_IDS`, and a strong `POSTGRES_PASSWORD`. Compose overrides `DATABASE_URL` with the container PostgreSQL URL, so you can leave the SQLite value in `.env` when running locally.

`ENVIRONMENT=production` is set by Compose. Production startup requires `ADMIN_IDS`.

### 2. Start the stack
```powershell
docker compose up -d --build
docker compose logs -f bot
```

### 3. Operate
```powershell
docker compose ps
docker compose restart bot
docker compose pull
docker compose up -d --build
docker compose down          # keep the database volume
docker compose down -v       # DANGER: also deletes all data
```

The PostgreSQL data lives in the named volume `postgres_data`. In the container, logs go to stdout (`docker compose logs -f bot`); local runs also write the rotating file configured by `LOG_FILE`.

Set `RUN_MIGRATIONS=false` on the bot service only if you manage migrations separately.

### Deploying without Docker
1. Provision PostgreSQL and create a database/user.
2. Install Python 3.11+ and `requirements.txt` in a virtual environment.
3. Set environment variables (do not rely on a committed `.env`).
4. Run `alembic upgrade head`.
5. Run `python -m app.main` under systemd, Supervisor, or a process manager.
6. Keep exactly one polling process per bot token.


## Vercel + Neon Deployment

Cheers Dating can run entirely serverless on **Vercel Functions** with the database on **Neon PostgreSQL**. Because Vercel functions are stateless and ephemeral, the bot runs in **webhook mode** (Telegram pushes updates to the function) instead of long polling. FSM state lives in PostgreSQL via the `fsm_states` table.

### 1. Provision the database

Create a Neon project in your organization and note the **pooled** connection string. Convert it to asyncpg form:

```
postgresql+asyncpg://user:pass@host-pooler.region.aws.neon.tech/db?ssl=require
```

Drop `channel_binding` (asyncpg negotiates it) and use `ssl=require`. Run migrations locally against Neon before the first deploy:

```powershell
$env:DATABASE_URL="postgresql+asyncpg://..."
.\.venv\Scripts\alembic.exe upgrade head
```

### 2. Prepare the repository

Vercel detects Python from `pyproject.toml`. The required files are already in the repo:

- `pyproject.toml` — declares dependencies and `[tool.vercel] entrypoint = "vercel_app:app"`
- `vercel_app.py` — FastAPI entrypoint with `/api/telegram`, `/api/health`, `/api/setup`, `/api/cron/broadcast`
- `vercel.json` — function configuration (max duration 60s)
- `.python-version` — Python 3.12
- `.vercelignore` — excludes `.venv`, tests, `.neon`, node_modules, etc.

### 3. Connect and deploy

```powershell
npm install -g vercel
vercel login
vercel link          # connect your GitHub repo
vercel --prod        # deploy to production
```

### 4. Set environment variables on Vercel

```powershell
vercel env add BOT_TOKEN           # your BotFather token
vercel env add ADMIN_IDS           # comma-separated Telegram IDs
vercel env add DATABASE_URL        # Neon pooled URL (asyncpg form)
vercel env add ENVIRONMENT         # production
vercel env add VERCEL              # true
vercel env add SERVERLESS          # true
vercel env add WEBHOOK_URL         # https://your-app.vercel.app
vercel env add WEBHOOK_SECRET      # A-Za-z0-9_- only (Telegram secret token)
vercel env add SETUP_TOKEN         # protects /api/setup
vercel env add CRON_SECRET         # protects /api/cron/broadcast
vercel env add AUTO_CREATE_TABLES  # false (migrations run separately)
vercel env add PREMIUM_ENABLED     # false (launch mode)
```

`LOG_FILE` is intentionally unset on Vercel (read-only filesystem); logs go to stdout.

### 5. Register the webhook

```powershell
vercel curl -X POST https://your-app.vercel.app/api/setup \
  -H "Authorization: Bearer <SETUP_TOKEN>"
```

This calls Telegram `setWebhook` with your `WEBHOOK_SECRET`. After this, the bot receives updates at `https://your-app.vercel.app/api/telegram`.

### 6. Admin broadcasts on serverless

Broadcasts are stored as `broadcast_jobs` rows and resume across invocations. To continue paused broadcasts, call:

```powershell
vercel curl -X POST https://your-app.vercel.app/api/cron/broadcast \
  -H "Authorization: Bearer <CRON_SECRET>"
```

You can wire this to a cron job (Vercel Cron or external) to run every few minutes.


## Production Checklist

- [ ] Rotate any token that has been shared or committed; store the new token in a secret manager or an untracked `.env`.
- [ ] Set `ENVIRONMENT=production` and a non-empty `ADMIN_IDS`.
- [ ] Use PostgreSQL, not SQLite, for concurrent production traffic.
- [ ] Run `alembic upgrade head` as part of every deployment.
- [ ] Restrict database network access and use a strong password.
- [ ] Back up PostgreSQL regularly and test restores.
- [ ] Keep `ALLOW_CONTACT_SHARING=false` unless you intentionally permit it.
- [ ] Keep `PREMIUM_ENABLED=false` until a payment provider and refund policy are in place, or grant premium manually.
- [ ] Run the bot as a non-root user (the provided Docker image does).
- [ ] Monitor logs for repeated errors and report volume.
- [ ] Review Telegram's Bot Terms and your local privacy/consumer obligations.
- [ ] Before running multiple bot processes, replace the in-memory FSM storage with Redis (`aiogram.fsm.storage.redis.RedisStorage`) and use a shared rate-limit store. Long polling with one process is the default.


## Testing

### Run the full suite
```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m compileall -q app
```

### What the tests cover

| Area | Coverage |
|------|----------|
| Validation | DOB/age, name, bio, city, photo count, interests |
| Users | Registration, photo replacement, profile editing, pause, deletion, underage/future DOB rejection |
| Discovery | Filters (age, gender, religion, city), candidate selection, daily limits, likes, passes, matches |
| Safety | Contact-info blocking, blocks, reports, bans, unmatch |
| Admin | Statistics, premium grants, premium/free limits, broadcast |
| Serverless | URL normalization, webhook settings validation, Vercel entrypoint exists |

The test suite uses an in-memory SQLite database, so it does not touch `cheers.db` or production data.

### Test count
67 tests (and growing).


## Troubleshooting

### `BOT_TOKEN is not set` / `does not look like a valid Telegram bot token`
Fill `BOT_TOKEN` in `.env` with the complete token, including the colon. Restart the bot after editing.

### `Database schema is missing. Run 'alembic upgrade head'`
Run `.\.venv\Scripts\alembic.exe upgrade head`. Alternatively set `AUTO_CREATE_TABLES=true` for a local-only quick start.

### `ADMIN_IDS must be set in production`
Set at least one numeric Telegram ID in `ADMIN_IDS`, or use `ENVIRONMENT=development` locally.

### `/admin` says "This command is for administrators only"
The numeric ID you used is not in `ADMIN_IDS`. Numeric IDs are not usernames. Update `.env`, restart, and try again.

### Bot does not respond
Check the console for `Connected as @...`, confirm the token is current, and make sure no other polling process is using the same token. Telegram allows only one `getUpdates` consumer at a time.

### `UNIQUE constraint failed: user_photos.user_id, user_photos.position`
This was fixed in the service layer by flushing photo deletions before inserts. Update to the current code and rerun the tests.

### PowerShell will not activate the virtual environment
Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or invoke `.\.venv\Scripts\python.exe` directly.

### Docker bot exits with a migration error
Check `docker compose logs db` for database startup problems and confirm `POSTGRES_PASSWORD` is set. The entrypoint retries ten times before failing.

### `alembic check` reports new operations
Create and review a migration with `alembic revision --autogenerate -m "change"`; do not edit an applied migration in production.

### Vercel webhook not receiving updates
1. Verify `WEBHOOK_URL` is set to `https://your-app.vercel.app` (no trailing slash).
2. Verify `WEBHOOK_SECRET` contains only `A-Za-z0-9_-`.
3. Run `POST /api/setup` with `Authorization: Bearer <SETUP_TOKEN>` to register the webhook.
4. Check `GET /api/health` returns `{"status":"ok","database":true}`.

---

## License

This project is provided for your private deployment. Add a license file before distributing it publicly.









