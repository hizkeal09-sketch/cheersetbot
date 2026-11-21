/**
 * Grand Ethio Techs - Configuration
 * Central configuration for the bot
 */

const config = {
  // Bot identity
  botName: 'Grand Ethio Techs',
  botUsername: '@GrandEthioTechsBot',

  // Default settings for new groups
  defaultTargetAdditions: 5,
  defaultLanguage: 'en',
  defaultChannelVerification: false,

  // Moderation defaults
  defaultWarningLimit: 3,
  defaultMuteDurationSeconds: 3600, // 1 hour
  defaultAntiSpam: true,
  defaultLinkRestrictions: false,

  // Pagination
  leaderboardLimit: 10,
  leaderboardExtendedLimit: 20,

  // Rate limiting (messages per minute per user)
  rateLimitWindowMs: 60000,
  rateLimitMaxMessages: 20,

  // Supported languages
  languages: ['en', 'am'],

  // Telegram API limits
  maxMessageLength: 4096,
  broadcastBatchDelayMs: 100,

  // Database
  poolMax: 10,
  poolIdleTimeoutMs: 30000,

  // Feature flags
  features: {
    directAddition: true,
    channelVerification: true,
    moderation: true,
    leaderboard: true,
    broadcast: true,
    multiLanguage: true
  }
};

module.exports = config;
