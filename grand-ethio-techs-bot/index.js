/**
 * Grand Ethio Techs - Telegram Member Booster and Group Management Bot
 * Main entry point (local development with polling)
 *
 * This file sets up the bot, registers all handlers, and starts polling.
 * For Vercel deployment, use api/webhook.js instead.
 */

require('dotenv').config();

const { Telegraf } = require('telegraf');
const config = require('./config/config');
const { pool } = require('./database/connection');
const db = require('./services/db');
const { handleCommands } = require('./handlers/commands');
const { handleMessages } = require('./handlers/messages');
const { handleCallbacks } = require('./handlers/callbacks');
const adminAuth = require('./middleware/adminAuth');
const { t, getUserLang, isAdmin, isSuperAdmin, logActivity } = require('./utils/helpers');

// ---------------------------------------------------------------------------
// Validate required environment variables
// ---------------------------------------------------------------------------
if (!process.env.BOT_TOKEN) {
  console.error('ERROR: BOT_TOKEN is not set in .env');
  console.error('Get your token from @BotFather and copy .env.example to .env');
  process.exit(1);
}

if (!process.env.DATABASE_URL) {
  console.error('ERROR: DATABASE_URL is not set in .env');
  console.error('Get your connection string from Neon Console');
  process.exit(1);
}

// ---------------------------------------------------------------------------
// Create bot instance
// ---------------------------------------------------------------------------
const bot = new Telegraf(process.env.BOT_TOKEN);

// ---------------------------------------------------------------------------
// Middleware: load user language and group context on every update
// ---------------------------------------------------------------------------
bot.use(async (ctx, next) => {
  try {
    // Attach helpers to context
    ctx.t = (key, vars) => t(key, vars, ctx.from ? ctx.from.id : null);
    ctx.getUserLang = () => getUserLang(ctx.from ? ctx.from.id : null);

    // Only process group/supergroup chats for group features
    if (ctx.chat && (ctx.chat.type === 'group' || ctx.chat.type === 'supergroup')) {
      await db.ensureGroup(ctx.chat);
      ctx.group = await db.getGroupByTelegramId(ctx.chat.id);
      ctx.groupSettings = await db.getGroupSettings(ctx.group.id);
    }

    // Check admin status
    if (ctx.from) {
      ctx.isBotAdmin = await isAdmin(ctx.from.id, ctx.chat ? ctx.chat.id : null);
      ctx.isSuperAdmin = isSuperAdmin(ctx.from.id);
    }

    await next();
  } catch (err) {
    console.error('Middleware error:', err);
    await next();
  }
});

// ---------------------------------------------------------------------------
// Register command handlers
// ---------------------------------------------------------------------------
handleCommands(bot);

// ---------------------------------------------------------------------------
// Register message handlers (new members, left members, text, etc.)
// ---------------------------------------------------------------------------
handleMessages(bot);

// ---------------------------------------------------------------------------
// Register callback query handlers (inline keyboards)
// ---------------------------------------------------------------------------
handleCallbacks(bot);

// ---------------------------------------------------------------------------
// Error handling
// ---------------------------------------------------------------------------
bot.catch((err, ctx) => {
  console.error('Bot error:', err);
  try {
    if (ctx && ctx.reply) {
      ctx.reply(ctx.t ? ctx.t('error_occurred') : 'An error occurred. Please try again.');
    }
  } catch (e) {
    console.error('Error reply failed:', e);
  }
});

// ---------------------------------------------------------------------------
// Export bot for serverless (Vercel) and start polling for local dev
// ---------------------------------------------------------------------------
module.exports = bot;

// When run directly (not imported), start polling
if (require.main === module) {
  const port = process.env.PORT || 3000;

  if (process.env.WEBHOOK_URL && process.env.NODE_ENV === 'production') {
    // Production webhook mode
    const express = require('express');
    const app = express();
    app.use(require('express').json());
    app.use(bot.webhookCallback('/api/webhook'));

    const webhookUrl = `${process.env.WEBHOOK_URL}/api/webhook`;
    bot.telegram.setWebhook(webhookUrl, {
      allowed_updates: [
        'message',
        'edited_message',
        'channel_post',
        'edited_channel_post',
        'inline_query',
        'chosen_inline_result',
        'callback_query',
        'shipping_query',
        'pre_checkout_query',
        'poll',
        'poll_answer',
        'my_chat_member',
        'chat_member',
        'chat_join_request'
      ]
    }).then(() => {
      console.log(`Webhook set to ${webhookUrl}`);
    }).catch((err) => {
      console.error('Failed to set webhook:', err);
    });

    app.listen(port, () => {
      console.log(`Grand Ethio Techs Bot running in webhook mode on port ${port}`);
    });
  } else {
    // Local development polling mode
    bot.launch({
      dropPendingUpdates: true,
      allowed_updates: [
        'message',
        'channel_post',
        'callback_query',
        'my_chat_member',
        'chat_member'
      ]
    }).then(() => {
      console.log('Grand Ethio Techs Bot is running in polling mode...');
    }).catch((err) => {
      console.error('Failed to launch bot:', err);
    });

    // Graceful stop
    process.once('SIGINT', () => bot.stop('SIGINT'));
    process.once('SIGTERM', () => bot.stop('SIGTERM'));
  }
}
