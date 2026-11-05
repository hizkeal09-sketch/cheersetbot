# 🍻 Cheers Dating

A production-minded Telegram dating bot for adults (18+) in Ethiopia, built with
**Python 3.11+**, **aiogram 3**, **SQLAlchemy 2**, **PostgreSQL/SQLite**, and
**Alembic**.

Cheers keeps Telegram identities private: members see a profile, never a
`@username` or numeric Telegram ID. Conversations unlock only after a mutual
like, and every member can report, block, pause, or delete their account.

---

## Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Quick start on Windows](#quick-start-on-windows)
- [Creating the Telegram bot](#creating-the-telegram-bot)
- [Configuration](#configuration)
- [Commands](#commands)
- [Premium modes](#premium-modes)
- [Database and migrations](#database-and-migrations)
- [Running tests](#running-tests)
- [Docker deployment](#docker-deployment)
- [Production checklist](#production-checklist)
- [Security and privacy](#security-and-privacy)
- [Troubleshooting](#troubleshooting)

---

## Features

**Onboarding and profiles**
- Mandatory 18+ confirmation plus date-of-birth validation.
- Name, date of birth, gender, dating preference, city, optional location,
  bio, interests, relationship intention, and up to 3 photos.
- Preview and confirmation before a profile goes live.
- Edit profile, manage photos, change preferences, pause/reactivate, or
  permanently delete the account.

**Discovery and matching**
- Card-based discovery with Like / Pass.
- Filters for age range, gender, and city.
- No self-discovery, no repeats, and no profiles you already liked or passed.
- Mutual likes create a match and notify both people.
- Daily discovery limits (configurable free and premium limits).
- "Who liked you" list; premium members can see everyone who liked them.

**Private messaging**
- Text and photo messages are relayed only between matched members.
- Telegram usernames, IDs, phone numbers, emails, and links are blocked in
  chat by default.
- Unmatch, block, and report flows.
- Reports capture a reason and optional details for moderators.

**Administration**
- Dashboard with registrations, active users, matches, open reports, bans, and
  premium counts.
- Report queue with ban, resolve, and dismiss actions.
- User search by database ID, Telegram ID, name, username, or city.
- Ban/unban, premium grant/revoke, broadcast to all active users, and an
  append-only admin audit trail.
- Admin access is restricted to Telegram IDs in `ADMIN_IDS`, enforced by both
  router filters and middleware.

**Platform**
- Async SQLAlchemy with SQLite for local development and PostgreSQL for
  production.
- Alembic migrations as the source of truth.
- Per-user sliding-window anti-spam throttling.
- Centralised error handler that logs failures and keeps the bot responsive.
- Dockerfile and Docker Compose stack with automatic migration on startup.
- Pytest suite (52 tests) covering validators, users, discovery, safety, admin,
  and premium logic.

---

## How it works

```text
Telegram update
      │
      ▼
Dispatcher (aiogram)
      │
 outer middlewares: database session → user loader/ban gate → throttle → registration gate
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

- **Handlers** translate Telegram events into service calls and render screens.
- **Services** contain business rules and are independently testable.
- **Models** use internal database IDs in callback data. Telegram IDs are never
  exposed on member-facing screens; only administrators see them.
- **FSM state** (registration, editing, chat relay, admin broadcast) is stored
  in memory. This is fine for one process; see
  [production checklist](#production-checklist) before scaling to multiple
  workers.

---

## Project structure

```text
app/
  main.py               # entrypoint: config, schema check, polling
  bot.py                # dispatcher and router/middleware wiring
  config.py             # typed settings from .env
  constants.py          # enums, labels, cities, interests, limits
  database/
    models.py           # User, Photo, Filter, Like, View, Match, Message,
                        # Block, Report, AdminAction, DailyUsage
    session.py          # async engine/session helpers
  handlers/             # Telegram routers by feature
  services/             # business logic
  middlewares/          # DB session, user, throttle, registration gate, errors
  keyboards/            # inline/reply keyboards
  states/forms.py       # FSM states
  utils/                # validators, time, rate limiting, rendering
migrations/             # Alembic environment and versions
tests/                  # pytest suite
Dockerfile
docker-compose.yml
docker-entrypoint.sh    # waits/retries and runs `alembic upgrade head`
.env.example            # documented configuration template
```

---

## Quick start on Windows

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

If PowerShell blocks activation, allow scripts for the current user once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Alternatively, skip activation and call the interpreter directly:
`.\.venv\Scripts\python.exe`.

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

`requirements.txt` is enough to run the bot; `requirements-dev.txt` adds pytest
and ruff.

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

`ADMIN_IDS` accepts comma-separated numeric Telegram IDs. To find yours, send
`/id` to [@userinfobot](https://t.me/userinfobot) or another ID helper.

> **Never commit `.env`.** It is already listed in `.gitignore`. If a token was
> ever pasted into a chat, issue a new token in BotFather with `/revoke` and use
> the new one.

### 5. Create the database schema

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

This creates `cheers.db` (SQLite) using the default `DATABASE_URL`.

For a throwaway local setup you can instead set `AUTO_CREATE_TABLES=true`, but
migrations are recommended and are what Docker uses.

### 6. Run the bot

```powershell
.\.venv\Scripts\python.exe -m app.main
```

You should see `Connected as @your_bot` in the logs. Open the bot in Telegram,
send `/start`, and complete registration. As an admin, `/admin` opens the
dashboard.

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

---

## Creating the Telegram bot

1. Open [@BotFather](https://t.me/BotFather), send `/newbot`, choose a display
   name and a username ending in `bot`.
2. Copy the token into `BOT_TOKEN` in `.env`. Treat it like a password.
3. Optional: use `/setdescription`, `/setabouttext`, and `/setuserpic` to
   brand the bot. The command list is published automatically on startup.
4. Optional: use `/setcommands` if you prefer to manage the menu manually:

   ```text
   start - Open the main menu
   discover - Meet someone new
   likes - See who liked you
   matches - Your matches and chats
   profile - View your profile
   editprofile - Edit your profile
   settings - Filters, pause and privacy
   premium - Premium features
   help - Help and safety
   ```

5. Start a private chat with the bot and send `/start`.

The bot uses long polling, so no public URL, HTTPS certificate, or port
forwarding is needed for the default setup.

---

## Configuration

All settings are read from `.env` (or real environment variables, which take
precedence). See `.env.example` for the full list.

| Variable | Default | Purpose |
| --- | --- | --- |
| `BOT_TOKEN` | — | Telegram bot token. **Required.** |
| `DATABASE_URL` | `sqlite+aiosqlite:///./cheers.db` | Async SQLAlchemy URL. PostgreSQL: `postgresql+asyncpg://user:pass@host:5432/db`. |
| `ADMIN_IDS` | empty | Comma-separated numeric Telegram IDs. Required in production. |
| `SUPPORT_CONTACT` | `@cheers_support` | Contact shown in help/premium screens. |
| `ENVIRONMENT` | `development` | `development`, `production`, or `test`. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_FILE` | `logs/cheers.log` | Rotating file log (5 MB × 5). Set empty to disable. |
| `APP_TIMEZONE` | `Africa/Addis_Ababa` | Timezone for daily limits and admin statistics. |
| `DROP_PENDING_UPDATES` | `false` | Drop queued updates on startup. |
| `AUTO_CREATE_TABLES` | `false` | Create tables without Alembic (development only). |
| `PREMIUM_ENABLED` | `false` | `false` unlocks premium for everyone (launch mode); `true` enforces gating. |
| `FREE_DAILY_DISCOVERIES` | `30` | Daily limit for free members. |
| `PREMIUM_DAILY_DISCOVERIES` | `300` | Daily limit for premium members. |
| `ALLOW_CONTACT_SHARING` | `false` | Allow phone/email/username/link sharing in chat. |
| `RATE_LIMIT_EVENTS` | `12` | Maximum events per user per window. |
| `RATE_LIMIT_WINDOW_SECONDS` | `10` | Sliding-window length. |
| `POSTGRES_PASSWORD` | — | Used only by Docker Compose for the database container. |

Daily counters reset at midnight in `APP_TIMEZONE`.

---

## Commands

| Command | Description |
| --- | --- |
| `/start` | Welcome screen and main menu. |
| `/help` | Help, safety guidance, and privacy notes. |
| `/profile` | View your profile as others see it. |
| `/editprofile` | Edit profile fields and photos. |
| `/discover` | Show the next compatible profile. |
| `/likes` | People who liked you. |
| `/matches` | Matches and open chats. |
| `/settings` | Discovery filters, pause/resume, privacy. |
| `/premium` | Premium status and benefits. |
| `/report` | Report a matched or recently seen member. |
| `/block` | Block a member. |
| `/pause` | Hide your profile from discovery. |
| `/deleteaccount` | Permanently delete your account and data. |
| `/admin` | Admin dashboard (staff only). |
| `/cancel` | Cancel the current form or flow. |
| `/end` | Leave the active chat relay. |

---

## Premium modes

**Launch mode — `PREMIUM_ENABLED=false` (default).** No payment provider is
connected yet, so premium features are unlocked for everyone at no cost. This
includes the larger discovery limit. Use this while growing the community.

**Paywall mode — `PREMIUM_ENABLED=true`.** Free members get
`FREE_DAILY_DISCOVERIES`; premium members get
`PREMIUM_DAILY_DISCOVERIES`, advanced filters, the full "who liked you" list,
and priority placement. Since there is no checkout integration yet, access is
granted by an administrator from the user detail screen. Payment integration
can be added later without changing the entitlement model.

To grant premium manually: `/admin` → **Users** → search → **Grant 30 days**.
Use **Revoke** to end it immediately.

---

## Database and migrations

Two database dialects are supported:

- **SQLite** for local development and tests: `sqlite+aiosqlite:///./cheers.db`
- **PostgreSQL** for production and Docker:
  `postgresql+asyncpg://user:password@host:5432/cheers`

Alembic reads `DATABASE_URL` from the app settings, so the URL is never stored
in `alembic.ini`.

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

The first migration creates: `users`, `user_photos`, `user_filters`, `likes`,
`profile_views`, `matches`, `messages`, `blocks`, `reports`, `admin_actions`,
and `daily_usage`.

To reset local data, stop the bot, delete `cheers.db`, and run
`alembic upgrade head` again. Never delete a production database.

---

## Running tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m compileall -q app
```

The test suite uses an in-memory SQLite database, so it does not touch
`cheers.db` or production data. It covers:

- DOB/age, name, bio, and account validation;
- registration, photo replacement, profile editing, pause, and deletion;
- filters, candidate selection, daily limits, likes, passes, and matches;
- contact-info blocking, blocks, reports, bans, and unmatch;
- admin statistics, premium grants, and premium/free limits.

---

## Docker deployment

Docker Compose runs PostgreSQL and the bot together. Alembic migrations are
applied automatically by `docker-entrypoint.sh`, with retries while PostgreSQL
starts.

### 1. Prepare the environment

```powershell
Copy-Item .env.example .env
notepad .env
```

Set `BOT_TOKEN`, `ADMIN_IDS`, and a strong `POSTGRES_PASSWORD`. Compose
overrides `DATABASE_URL` with the container PostgreSQL URL, so you can leave
the SQLite value in `.env` when running locally.

`ENVIRONMENT=production` is set by Compose. Production startup requires
`ADMIN_IDS`.

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

The PostgreSQL data lives in the named volume `postgres_data`. In the container,
logs go to stdout (`docker compose logs -f bot`); local runs also write the
rotating file configured by `LOG_FILE`.

Set `RUN_MIGRATIONS=false` on the bot service only if you manage migrations
separately.

### Deploying without Docker

1. Provision PostgreSQL and create a database/user.
2. Install Python 3.11+ and `requirements.txt` in a virtual environment.
3. Set environment variables (do not rely on a committed `.env`).
4. Run `alembic upgrade head`.
5. Run `python -m app.main` under systemd, Supervisor, or a process manager.
6. Keep exactly one polling process per bot token.

---

## Production checklist

- [ ] Rotate any token that has been shared or committed; store the new token in
      a secret manager or an untracked `.env`.
- [ ] Set `ENVIRONMENT=production` and a non-empty `ADMIN_IDS`.
- [ ] Use PostgreSQL, not SQLite, for concurrent production traffic.
- [ ] Run `alembic upgrade head` as part of every deployment.
- [ ] Restrict database network access and use a strong password.
- [ ] Back up PostgreSQL regularly and test restores.
- [ ] Keep `ALLOW_CONTACT_SHARING=false` unless you intentionally permit it.
- [ ] Keep `PREMIUM_ENABLED=false` until a payment provider and refund policy
      are in place, or grant premium manually.
- [ ] Run the bot as a non-root user (the provided image does).
- [ ] Monitor logs for repeated errors and report volume.
- [ ] Review Telegram's Bot Terms and your local privacy/consumer obligations.
- [ ] Before running multiple bot processes, replace the in-memory FSM storage
      with Redis (`aiogram.fsm.storage.redis.RedisStorage`) and use a shared
      rate-limit store. Long polling with one process is the default.

---

## Security and privacy

- **No hardcoded secrets.** Configuration comes from environment variables;
  `alembic.ini` contains no URL; `.env` is gitignored.
- **Telegram identity is hidden.** Member screens and callback data use internal
  database IDs. Telegram IDs appear only in admin views.
- **Matched-only messaging.** Messages are relayed through the bot; members
  never receive each other's Telegram account details.
- **Contact blocking.** Phone numbers, emails, `@usernames`, and URLs are
  rejected by default, with `ALLOW_CONTACT_SHARING` as an explicit opt-out.
- **SQL injection protection.** All queries use SQLAlchemy expressions and bound
  parameters.
- **Rate limiting.** A per-user sliding window rejects floods before handlers
  run.
- **Admin defence in depth.** Admin routers are filtered by Telegram ID and
  protected again by middleware; unauthorised callbacks receive an alert.
- **Audit trail.** Bans, unbans, report decisions, premium changes, and
  broadcasts are recorded in `admin_actions`.
- **Account deletion.** `/deleteaccount` removes the profile, photos, likes,
  matches, messages, blocks, reports involving the account, and daily usage via
  database cascades. Admin audit entries are retained with the target user
  reference cleared, so moderation decisions remain accountable.
- **Age gate.** Users must confirm 18+ and submit a valid adult date of birth.
  This is self-attestation, not government ID verification; add identity
  verification if your jurisdiction or risk model requires it.
- **Photos** are stored as Telegram `file_id` references, not downloaded to the
  server. Telegram hosts the media under its own retention rules.

Report suspected abuse to your configured `SUPPORT_CONTACT`. In an emergency,
contact local authorities.

---

## Troubleshooting

**`BOT_TOKEN is not set` / `does not look like a valid Telegram bot token`**
Fill `BOT_TOKEN` in `.env` with the complete token, including the colon.
Restart the bot after editing.

**`Database schema is missing. Run 'alembic upgrade head'`**
Run `.\.venv\Scripts\alembic.exe upgrade head`. Alternatively set
`AUTO_CREATE_TABLES=true` for a local-only quick start.

**`ADMIN_IDS must be set in production`**
Set at least one numeric Telegram ID in `ADMIN_IDS`, or use
`ENVIRONMENT=development` locally.

**`/admin` says "This command is for administrators only"**
The numeric ID you used is not in `ADMIN_IDS`. Numeric IDs are not usernames.
Update `.env`, restart, and try again.

**Bot does not respond**
Check the console for `Connected as @...`, confirm the token is current, and
make sure no other polling process is using the same token. Telegram allows
only one `getUpdates` consumer at a time.

**`UNIQUE constraint failed: user_photos.user_id, user_photos.position`**
This was fixed in the service layer by flushing photo deletions before inserts.
Update to the current code and rerun the tests.

**PowerShell will not activate the virtual environment**
Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or invoke
`.\.venv\Scripts\python.exe` directly.

**Docker bot exits with a migration error**
Check `docker compose logs db` for database startup problems and confirm
`POSTGRES_PASSWORD` is set. The entrypoint retries ten times before failing.

**`alembic check` reports new operations**
Create and review a migration with
`alembic revision --autogenerate -m "change"`; do not edit an applied migration
in production.

---

## License

This project is provided for your private deployment. Add a license file before
distributing it publicly.
