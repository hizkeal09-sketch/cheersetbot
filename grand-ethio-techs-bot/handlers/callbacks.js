/**
 * Grand Ethio Techs - Callback Query Handlers
 * Handles inline keyboard button presses
 */

const db = require('../services/db');
const { t, isAdmin, isSuperAdmin, logActivity, getUserLang } = require('../utils/helpers');
const config = require('../config/config');

/**
 * Register all callback query handlers on the bot
 */
function handleCallbacks(bot) {
  bot.action(/^admin_(.+)$/, async (ctx) => {
    const action = ctx.match[1];
    await db.upsertUser(ctx.from);
    const isGroupAdmin = await isAdmin(ctx.from.id, ctx.chat.id);
    const isSuper = isSuperAdmin(ctx.from.id);
    if (!isGroupAdmin && !isSuper) {
      await ctx.answerCbQuery(ctx.t('admin_only', {}, ctx.from.id));
      return;
    }

    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const settings = await db.getGroupSettings(group.id);
    const target = settings ? settings.target_additions : config.defaultTargetAdditions;
    const channelMode = settings ? settings.channel_verification : false;

    if (action === 'stats') {
      const stats = await db.getGroupStats(group.id);
      await ctx.editMessageText(
        ctx.t('stats_title', { group: ctx.chat.title }, ctx.from.id) + '\n\n' +
        ctx.t('stats_total_additions', { count: stats.totalAdditions }, ctx.from.id) + '\n' +
        ctx.t('stats_verified', { count: stats.verifiedMembers }, ctx.from.id) + '\n' +
        ctx.t('stats_pending', { count: stats.pendingMembers }, ctx.from.id) + '\n' +
        ctx.t('stats_channels', { count: stats.requiredChannels }, ctx.from.id) +
        '\n\nTarget additions: ' + target +
        '\nChannel verification: ' + (channelMode ? 'Enabled' : 'Disabled'),
        {
          reply_markup: {
            inline_keyboard: [
              [{ text: 'Back', callback_data: 'admin_back' }]
            ]
          }
        }
      );
    } else if (action === 'channels') {
      const channels = await db.getChannels(group.id);
      let text = ctx.t('channel_list', { channels: channels.length ? channels.map(c => c.channel_username || c.channel_id).join('\n') : 'None' }, ctx.from.id);
      await ctx.editMessageText(text, {
        reply_markup: {
          inline_keyboard: [
            [{ text: 'Add Channel', callback_data: 'admin_add_channel' }],
            [{ text: 'Back', callback_data: 'admin_back' }]
          ]
        }
      });
    } else if (action === 'settings') {
      await ctx.editMessageText(
        ctx.t('settings_title', {}, ctx.from.id) + '\n\n' +
        ctx.t('settings_target', { target: target }, ctx.from.id) + '\n' +
        ctx.t('settings_channel_mode', { mode: channelMode ? 'Enabled' : 'Disabled' }, ctx.from.id) + '\n' +
        ctx.t('settings_language', { lang: (settings ? settings.language : 'en').toUpperCase() }, ctx.from.id),
        {
          reply_markup: {
            inline_keyboard: [
              [{ text: 'Back', callback_data: 'admin_back' }]
            ]
          }
        }
      );
    } else if (action === 'leaderboard') {
      const leaderboard = await db.getLeaderboard(group.id, config.leaderboardLimit);
      let text = ctx.t('leaderboard_title', {}, ctx.from.id) + '\n\n';
      if (leaderboard.length === 0) {
        text += ctx.t('leaderboard_empty', {}, ctx.from.id);
      } else {
        leaderboard.forEach((entry, i) => {
          text += `#${i + 1}. ${entry.user_id} - ${entry.additions} additions\n`;
        });
      }
      await ctx.editMessageText(text, {
        reply_markup: {
          inline_keyboard: [
            [{ text: 'Back', callback_data: 'admin_back' }]
          ]
        }
      });
    } else if (action === 'moderation') {
      await ctx.editMessageText(
        'Moderation Settings\n\nUse /warn, /mute, /ban, /unban commands.',
        {
          reply_markup: {
            inline_keyboard: [
              [{ text: 'Back', callback_data: 'admin_back' }]
            ]
          }
        }
      );
    } else if (action === 'welcome') {
      await ctx.editMessageText(
        ctx.t('welcome_enabled', {}, ctx.from.id),
        {
          reply_markup: {
            inline_keyboard: [
              [{ text: 'Back', callback_data: 'admin_back' }]
            ]
          }
        }
      );
    } else if (action === 'exempt') {
      const exemptions = await db.getExemptions(group.id);
      let text = 'Exempted Members:\n\n';
      if (exemptions.length === 0) {
        text += 'None';
      } else {
        exemptions.forEach(e => {
          text += `- ${e.user_telegram_id}\n`;
        });
      }
      await ctx.editMessageText(text, {
        reply_markup: {
          inline_keyboard: [
            [{ text: 'Back', callback_data: 'admin_back' }]
          ]
        }
      });
    } else if (action === 'activity') {
      const logs = await db.getActivityLogs(group.id, 10);
      let text = 'Recent Activity:\n\n';
      logs.forEach(l => {
        text += `- ${l.action}: ${l.details}\n`;
      });
      await ctx.editMessageText(text, {
        reply_markup: {
          inline_keyboard: [
            [{ text: 'Back', callback_data: 'admin_back' }]
          ]
        }
      });
    } else if (action === 'back') {
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
      await ctx.editMessageText(
        ctx.t('admin_dashboard', {}, ctx.from.id) +
        '\n\nTarget additions: ' + target +
        '\nChannel verification: ' + (channelMode ? 'Enabled' : 'Disabled'),
        { reply_markup: keyboard }
      );
    }
    await ctx.answerCbQuery();
  });
}

module.exports = { handleCallbacks };
