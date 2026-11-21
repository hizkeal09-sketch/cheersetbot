/**
 * Grand Ethio Techs - Admin Authorization Middleware
 * Verifies Telegram administrator permissions before admin commands
 */

const { Telegraf } = require('telegraf');
const { isAdmin, isSuperAdmin, t, logActivity } = require('../utils/helpers');

/**
 * Check if a user is a Telegram chat administrator (actual Telegram admin status)
 * This queries Telegram API to verify real admin rights
 */
async function isTelegramAdmin(ctx, userId) {
  if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) {
    return false;
  }
  try {
    const chatMember = await ctx.telegram.getChatMember(ctx.chat.id, userId);
    const status = chatMember.status;
    return status === 'creator' || status === 'administrator';
  } catch (err) {
    console.error('getChatMember error:', err.message);
    return false;
  }
}

/**
 * Middleware factory: only allow if user is a real Telegram admin or super admin
 */
function requireAdmin() {
  return async (ctx, next) => {
    const userId = ctx.from ? ctx.from.id : null;
    if (!userId) return;

    // Super admins bypass
    if (isSuperAdmin(userId)) {
      return await next();
    }

    // Must be in a group
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) {
      await ctx.reply(ctx.t('not_admin'));
      return;
    }

    // Check Telegram admin status
    const admin = await isTelegramAdmin(ctx, userId);
    if (!admin) {
      await ctx.reply(ctx.t('not_admin'));
      await logActivity(ctx.chat.id, userId, 'unauthorized_admin_command', 'Attempted admin command without Telegram admin rights');
      return;
    }

    await next();
  };
}

/**
 * Middleware: only allow super admins
 */
function requireSuperAdmin() {
  return async (ctx, next) => {
    const userId = ctx.from ? ctx.from.id : null;
    if (!userId) return;
    if (!isSuperAdmin(userId)) {
      await ctx.reply(ctx.t('super_admin_only'));
      return;
    }
    await next();
  };
}

/**
 * Middleware: ensure bot is admin with restrict rights
 */
async function ensureBotAdmin(ctx) {
  if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return false;
  try {
    const botId = ctx.botInfo ? ctx.botInfo.id : null;
    if (!botId) return false;
    const chatMember = await ctx.telegram.getChatMember(ctx.chat.id, botId);
    return chatMember.status === 'creator' || chatMember.status === 'administrator';
  } catch (err) {
    return false;
  }
}

module.exports = {
  requireAdmin,
  requireSuperAdmin,
  isTelegramAdmin,
  ensureBotAdmin
};
