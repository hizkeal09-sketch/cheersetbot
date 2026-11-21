/**
 * Grand Ethio Techs - Vercel Webhook Handler
 * Serverless entry point for Vercel deployment
 */

const { Telegraf } = require('telegraf');
require('dotenv').config();

const { handleCommands } = require('../handlers/commands');
const { handleMessages } = require('../handlers/messages');
const { handleCallbacks } = require('../handlers/callbacks');
const db = require('../services/db');

// Create bot instance
const bot = new Telegraf(process.env.BOT_TOKEN);

// Register handlers
handleCommands(bot);
handleMessages(bot);
handleCallbacks(bot);

// Error handling
bot.catch((err, ctx) => {
  console.error('Bot error:', err);
});

// Export the webhook handler for Vercel
module.exports = async (req, res) => {
  try {
    // Handle webhook updates
    if (req.method === 'POST' && req.body && req.body.update_id) {
      await bot.handleUpdate(req.body, res);
      return res.status(200).send('OK');
    }

    // Health check
    res.status(200).send('Grand Ethio Techs Bot is running');
  } catch (err) {
    console.error('Webhook error:', err);
    res.status(500).send('Internal Server Error');
  }
};
