# Grand Ethio Techs Bot

Telegram Member Booster and Group Management Bot.

## Features
- Direct member addition verification (permanent counting)
- Optional channel subscription verification
- Multi-group support
- Administrator dashboard via inline keyboards
- Leaderboard and statistics
- Moderation tools
- English and Amharic language support

## Setup

1. Copy `.env.example` to `.env` and fill in your values.
2. Run `npm install` to install dependencies.
3. Run `npm run setup-db` to create database tables in Neon PostgreSQL.
4. Run `npm start` to start the bot locally (polling mode).

## Deployment

Deploy to Vercel using the `api/webhook.js` serverless function.

Never commit your `.env` file to GitHub.
