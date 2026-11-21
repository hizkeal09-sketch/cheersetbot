/**
 * Grand Ethio Techs - Command Handlers
 * All bot command handlers
 */

const db = require('../services/db');
const { t, getUserLang, isAdmin, isSuperAdmin, formatUserName, formatMention, logActivity, getRemainingAdditions, isVerificationComplete } = require('../utils/helpers');
const config = require('../config/config');

/**
 * Register all command handlers on the bot
 */
function handleCommands(bot) {

  // -------------------------------------------------------------------------
  // /start
  // -------------------------------------------------------------------------
  bot.command('start', async (ctx) => {
    await db.upsertUser(ctx.from);
    const lang = await getUserLang(ctx.from.id);
    const isGroup = ctx.chat && (ctx.chat.type === 'group' || ctx.chat.type === 'supergroup');

    if (isGroup) {
      await db.ensureGroup(ctx.chat);
      const group = await db.getGroupByTelegramId(ctx.chat.id);
      await logActivity(group.id, ctx.from.id, 'start', 'Bot started in group');
      await ctx.reply(ctx.t('bot_added', { group: ctx.chat.title }, ctx.from.id));
    } else {
      await ctx.reply(ctx.t('help', {}, ctx.from.id), {
        parse_mode: 'Markdown'
      });
    }
  });

  // -------------------------------------------------------------------------
  // /help
  // -------------------------------------------------------------------------
  bot.command('help', async (ctx) => {
    await db.upsertUser(ctx.from);
    await ctx.reply(ctx.t('help', {}, ctx.from.id), {
      parse_mode: 'Markdown'
    });
  });

  // -------------------------------------------------------------------------
  // /check - check verification status
  // -------------------------------------------------------------------------
  bot.command('check', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) {
      await ctx.reply(ctx.t('not_admin', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const verification = await db.getVerification(group.id, ctx.from.id);
    const settings = await db.getGroupSettings(group.id);
    const target = settings ? settings.target_additions : config.defaultTargetAdditions;
    const current = await db.getAdditionCount(group.id, ctx.from.id);

    let additionsStatus = verification ? verification.additions_completed : false;
    let channelStatus = verification ? verification.channels_subscribed : true;
    const channelVerificationEnabled = settings ? settings.channel_verification : false;

    if (channelVerificationEnabled) {
      channelStatus = verification ? verification.channels_subscribed : false;
    }

    const additionsDone = current >= target;
    const channelText = channelVerificationEnabled
      ? (channelStatus ? 'Done' : 'Not done')
      : 'Not required';

    const overall = isVerificationComplete(group.id, ctx.from.id) ? 'Verified' : 'Pending';

    await ctx.reply(
      ctx.t('verification_status', {
        status: overall,
        current: current,
        target: target,
        channelStatus: channelText
      }, ctx.from.id)
    );
  });

  // -------------------------------------------------------------------------
  // /instructions - show verification instructions
  // -------------------------------------------------------------------------
  bot.command('instructions', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const settings = await db.getGroupSettings(group.id);
    const target = settings ? settings.target_additions : config.defaultTargetAdditions;
    const current = await db.getAdditionCount(group.id, ctx.from.id);
    const remaining = Math.max(0, target - current);

    let text = ctx.t('verification_instructions', {
      target: target,
      current: current
    }, ctx.from.id);

    if (settings && settings.channel_verification) {
      text += '\n\n' + ctx.t('channel_required', {}, ctx.from.id);
    }

    await ctx.reply(text);
  });

  // -------------------------------------------------------------------------
  // /language - change language
  // -------------------------------------------------------------------------
  bot.command('language', async (ctx) => {
    await db.upsertUser(ctx.from);
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const lang = args[0];
    if (lang === 'en' || lang === 'am') {
      await db.setUserLanguage(ctx.from.id, lang);
      await ctx.reply(ctx.t('language_set', { lang: lang.toUpperCase() }, ctx.from.id));
    } else {
      const current = await getUserLang(ctx.from.id);
      await ctx.reply(ctx.t('language_current', { lang: current.toUpperCase() }, ctx.from.id));
    }
  });

  // -------------------------------------------------------------------------
  // /admin - administrator dashboard
  // -------------------------------------------------------------------------
  bot.command('admin', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) {
      await ctx.reply(ctx.t('not_admin', {}, ctx.from.id));
      return;
    }
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const settings = await db.getGroupSettings(group.id);
    const target = settings ? settings.target_additions : config.defaultTargetAdditions;
    const channelMode = settings ? settings.channel_verification : false;

    const keyboard = {
      inline_keyboard: [
        [
          { text: ctx.t('admin_menu_stats', {}, ctx.from.id), callback_data: 'admin_stats' },
          { text: ctx.t('admin_menu_channels', {}, ctx.from.id), callback_data: 'admin_channels' }
        ],
        [
          { text: ctx.t('admin_menu_settings', {}, ctx.from.id), callback_data: 'admin_settings' },
          { text: ctx.t('admin_menu_leaderboard', {}, ctx.from.id), callback_data: 'admin_leaderboard' }
        ],
        [
          { text: ctx.t('admin_menu_moderation', {}, ctx.from.id), callback_data: 'admin_moderation' },
          { text: ctx.t('admin_menu_welcome', {}, ctx.from.id), callback_data: 'admin_welcome' }
        ],
        [
          { text: ctx.t('admin_menu_exempt', {}, ctx.from.id), callback_data: 'admin_exempt' },
          { text: ctx.t('admin_menu_activity', {}, ctx.from.id), callback_data: 'admin_activity' }
        ],
        [
          { text: ctx.t('back_to_menu', {}, ctx.from.id), callback_data: 'admin_back' }
        ]
      ]
    };

    await ctx.reply(
      ctx.t('admin_dashboard', {}, ctx.from.id) +
      '\n\nTarget additions: ' + target +
      '\nChannel verification: ' + (channelMode ? 'Enabled' : 'Disabled'),
      {
        reply_markup: keyboard
      }
    );
    await logActivity(group.id, ctx.from.id, 'admin_dashboard', 'Opened admin dashboard');
  });

  // -------------------------------------------------------------------------
  // /stats
  // -------------------------------------------------------------------------
  bot.command('stats', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const stats = await db.getGroupStats(group.id);
    await ctx.reply(
      ctx.t('stats_title', { group: ctx.chat.title }, ctx.from.id) + '\n\n' +
      ctx.t('stats_total_additions', { count: stats.totalAdditions }, ctx.from.id) + '\n' +
      ctx.t('stats_verified', { count: stats.verifiedMembers }, ctx.from.id) + '\n' +
      ctx.t('stats_pending', { count: stats.pendingMembers }, ctx.from.id) + '\n' +
      ctx.t('stats_channels', { count: stats.requiredChannels }, ctx.from.id)
    );
    await logActivity(group.id, ctx.from.id, 'stats', 'Viewed group statistics');
  });

  // -------------------------------------------------------------------------
  // /settarget
  // -------------------------------------------------------------------------
  bot.command('settarget', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const target = parseInt(args[0], 10);
    if (!target || target < 1) {
      await ctx.reply(ctx.t('invalid_target', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    await db.setTargetAdditions(group.id, target);
    await ctx.reply(ctx.t('target_set', { target: target }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'set_target', `Target set to ${target}`);
  });

  // -------------------------------------------------------------------------
  // /channels
  // -------------------------------------------------------------------------
  bot.command('channels', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const channels = await db.getChannels(group.id);
    if (channels.length === 0) {
      await ctx.reply(ctx.t('channel_list_empty', {}, ctx.from.id));
      return;
    }
    const list = channels.map(c => c.channel_username || c.channel_id).join('\n');
    await ctx.reply(ctx.t('channel_list', { channels: list }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'view_channels', 'Viewed required channels');
  });

  // -------------------------------------------------------------------------
  // /channelmode
  // -------------------------------------------------------------------------
  bot.command('channelmode', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const enable = args[0] === 'enable' || args[0] === 'on' || args[0] === '1';
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    await db.toggleChannelVerification(group.id, enable);
    await ctx.reply(enable ? ctx.t('channel_mode_enabled', {}, ctx.from.id) : ctx.t('channel_mode_disabled', {}, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'toggle_channel_verification', `Channel verification ${enable ? 'enabled' : 'disabled'}`);
  });

  // -------------------------------------------------------------------------
  // /verify
  // -------------------------------------------------------------------------
  bot.command('verify', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const targetId = parseInt(args[0], 10);
    if (!targetId) {
      await ctx.reply(ctx.t('member_not_found', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    await db.setVerified(group.id, targetId, true);
    await ctx.reply(ctx.t('verify_member', { user: targetId }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'manual_verify', `Verified user ${targetId}`);
  });

  // -------------------------------------------------------------------------
  // /exempt
  // -------------------------------------------------------------------------
  bot.command('exempt', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const targetId = parseInt(args[0], 10);
    if (!targetId) {
      await ctx.reply(ctx.t('member_not_found', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    await db.addExemption(group.id, targetId, 'Manual exemption', ctx.from.id);
    await ctx.reply(ctx.t('exempt_added', { user: targetId }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'add_exemption', `Exempted user ${targetId}`);
  });

  // -------------------------------------------------------------------------
  // /setcount
  // -------------------------------------------------------------------------
  bot.command('setcount', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const targetId = parseInt(args[0], 10);
    const count = parseInt(args[1], 10);
    if (!targetId || count < 0) {
      await ctx.reply(ctx.t('invalid_target', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    await db.setManualCount(group.id, targetId, count, ctx.from.id);
    await ctx.reply(ctx.t('count_set', { user: targetId, count: count }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'set_count', `Set count for ${targetId} to ${count}`);
  });

  // -------------------------------------------------------------------------
  // /resetcount
  // -------------------------------------------------------------------------
  bot.command('resetcount', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const targetId = parseInt(args[0], 10);
    if (!targetId) {
      await ctx.reply(ctx.t('member_not_found', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    await db.resetCount(group.id, targetId, ctx.from.id);
    await ctx.reply(ctx.t('count_reset', { user: targetId }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'reset_count', `Reset count for ${targetId}`);
  });

  // -------------------------------------------------------------------------
  // /leaderboard
  // -------------------------------------------------------------------------
  bot.command('leaderboard', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const leaderboard = await db.getLeaderboard(group.id, config.leaderboardLimit);
    if (leaderboard.length === 0) {
      await ctx.reply(ctx.t('leaderboard_empty', {}, ctx.from.id));
      return;
    }
    let text = ctx.t('leaderboard_title', {}, ctx.from.id) + '\n\n';
    leaderboard.forEach((entry, i) => {
      text += ctx.t('leaderboard_entry', {
        rank: i + 1,
        name: entry.user_id,
        count: entry.additions
      }, ctx.from.id) + '\n';
    });
    await ctx.reply(text);
  });

  // -------------------------------------------------------------------------
  // /settings
  // -------------------------------------------------------------------------
  bot.command('settings', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const settings = await db.getGroupSettings(group.id);
    const target = settings ? settings.target_additions : config.defaultTargetAdditions;
    const channelMode = settings ? settings.channel_verification : false;
    const lang = settings ? settings.language : 'en';
    const antiSpam = settings ? settings.anti_spam : true;
    const warningLimit = settings ? settings.warning_limit : config.defaultWarningLimit;

    await ctx.reply(
      ctx.t('settings_title', {}, ctx.from.id) + '\n\n' +
      ctx.t('settings_target', { target: target }, ctx.from.id) + '\n' +
      ctx.t('settings_channel_mode', { mode: channelMode ? 'Enabled' : 'Disabled' }, ctx.from.id) + '\n' +
      ctx.t('settings_language', { lang: lang.toUpperCase() }, ctx.from.id) + '\n' +
      ctx.t('settings_anti_spam', { status: antiSpam ? 'Enabled' : 'Disabled' }, ctx.from.id) + '\n' +
      ctx.t('settings_warning_limit', { limit: warningLimit }, ctx.from.id)
    );
  });

  // -------------------------------------------------------------------------
  // /broadcast
  // -------------------------------------------------------------------------
  bot.command('broadcast', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    const admin = await isAdmin(ctx.from.id, ctx.chat.id);
    if (!admin && !isSuperAdmin(ctx.from.id)) {
      await ctx.reply(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }
    const args = ctx.message.text.trim().split(/\s+/).slice(1);
    const message = args.join(' ');
    if (!message) {
      await ctx.reply('Please provide a message to broadcast.');
      return;
    }
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const members = await db.getPendingVerifications(group.id);
    let sent = 0;
    for (const m of members) {
      try {
        await ctx.telegram.sendMessage(m.user_telegram_id, message);
        sent++;
      } catch (e) {
        // user may have blocked bot
      }
    }
    await ctx.reply(ctx.t('broadcast_sent', { count: sent }, ctx.from.id));
    await logActivity(group.id, ctx.from.id, 'broadcast', `Sent to ${sent} recipients`);
  });
}

module.exports = { handleCommands };
