/**
 * Grand Ethio Techs - Message Handlers
 * Handles new_chat_members, left_chat_member, text messages
 */

const db = require('../services/db');
const { t, formatUserName, formatMention, logActivity, isVerificationComplete, isAdmin, isSuperAdmin, getUserLang } = require('../utils/helpers');
const config = require('../config/config');

/**
 * Register all message handlers on the bot
 */
function handleMessages(bot) {

  // -------------------------------------------------------------------------
  // Handle new chat members (direct member addition detection)
  // -------------------------------------------------------------------------
  bot.on('new_chat_members', async (ctx) => {
    await db.upsertUser(ctx.from);
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;

    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const settings = await db.getGroupSettings(group.id);
    const target = settings ? settings.target_additions : config.defaultTargetAdditions;

    const newMembers = ctx.message.new_chat_members || [];
    const adder = ctx.from; // the person who added them (or the bot/joined via link if unattributed)

    for (const member of newMembers) {
      // Skip bots
      if (member.is_bot) continue;

      await db.upsertUser(member);

      // Check if this is an unattributed join (adder is the member themselves, or adder is the bot)
      const isSelfJoin = adder && adder.id === member.id;
      const isBotAdd = adder && adder.is_bot;
      const isUnattributed = isSelfJoin || isBotAdd || !adder;

      // Check if already existing member (rejoin) - check verifications table
      const existingVerification = await db.getVerification(group.id, member.id);
      const alreadyMember = existingVerification !== null;

      let counted = false;

      if (!isUnattributed && !alreadyMember && adder && !adder.is_bot) {
        // Attempt to record the addition
        counted = await db.recordMemberAddition(
          group.id,
          adder.id,
          member.id,
          'new_chat_members'
        );
      }

      // Ensure verification record exists for the new member
      await db.ensureVerification(group.id, member.id);

      // If the adder got credit, update their additions_completed status
      if (counted && adder && !adder.is_bot) {
        const adderCount = await db.getAdditionCount(group.id, adder.id);
        const additionsDone = adderCount >= target;
        await db.setAdditionsCompleted(group.id, adder.id, additionsDone);

        // Notify the adder
        try {
          const remaining = Math.max(0, target - adderCount);
          await ctx.telegram.sendMessage(
            adder.id,
            ctx.t('addition_counted', {
              name: formatUserName(member),
              current: adderCount,
              target: target
            }, adder.id)
          );
        } catch (e) {
          // user may have blocked bot
        }
      }

      // Notify new member of welcome and restrictions (unless exempt)
      const isExempt = await db.isExempt(group.id, member.id);
      if (!isExempt) {
        // Restrict the new member from sending messages
        try {
          await ctx.telegram.restrictChatMember(group.telegram_id, member.id, {
            can_send_messages: false,
            can_send_media_messages: false,
            can_send_polls: false,
            can_send_other_messages: false,
            can_add_web_page_previews: false,
            can_change_info: false,
            can_invite_users: false,
            can_pin_messages: false
          });
        } catch (e) {
          console.error('Failed to restrict new member:', e.message);
        }

        const currentCount = await db.getAdditionCount(group.id, member.id);
        const remaining = Math.max(0, target - currentCount);
        await ctx.telegram.sendMessage(
          member.id,
          ctx.t('welcome_new_member', {
            name: formatUserName(member),
            group: ctx.chat.title,
            target: target,
            current: currentCount,
            remaining: remaining
          }, member.id)
        );
      } else {
        // Exempt member - mark verified
        await db.setVerified(group.id, member.id, true);
        await db.setAdditionsCompleted(group.id, member.id, true);
        await ctx.telegram.sendMessage(
          member.id,
          ctx.t('welcome_exempt', { name: formatUserName(member), group: ctx.chat.title }, member.id)
        );
      }

      await logActivity(group.id, adder ? adder.id : null, 'new_member_join', `New member ${member.id} joined, counted=${counted}`);
    }
  });

  // -------------------------------------------------------------------------
  // Handle left chat members
  // -------------------------------------------------------------------------
  bot.on('left_chat_member', async (ctx) => {
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const leftMember = ctx.message.left_chat_member;
    if (leftMember && !leftMember.is_bot) {
      await logActivity(group.id, leftMember.id, 'member_left', `Member ${leftMember.id} left`);
      // Note: addition records are NOT deleted (permanent counting policy)
    }
  });

  // -------------------------------------------------------------------------
  // Handle text messages in groups (mute unverified members)
  // -------------------------------------------------------------------------
  bot.on('text', async (ctx) => {
    if (!ctx.chat || (ctx.chat.type !== 'group' && ctx.chat.type !== 'supergroup')) return;
    await db.upsertUser(ctx.from);

    await db.ensureGroup(ctx.chat);
    const group = await db.getGroupByTelegramId(ctx.chat.id);
    const settings = await db.getGroupSettings(group.id);

    // Check if user is admin - admins bypass restrictions
    const isGroupAdmin = await isAdmin(ctx.from.id, ctx.chat.id);
    const isSuper = isSuperAdmin(ctx.from.id);
    if (isGroupAdmin || isSuper) return;

    // Check exemption
    const isExempt = await db.isExempt(group.id, ctx.from.id);
    if (isExempt) return;

    // Check verification
    const complete = await isVerificationComplete(group.id, ctx.from.id);
    if (!complete) {
      // Delete the message and remind them
      try {
        await ctx.deleteMessage();
      } catch (e) {
        // cannot delete
      }
      const target = settings ? settings.target_additions : config.defaultTargetAdditions;
      const current = await db.getAdditionCount(group.id, ctx.from.id);
      const remaining = Math.max(0, target - current);
      try {
        await ctx.telegram.sendMessage(
          ctx.from.id,
          ctx.t('verification_instructions', {
            target: target,
            current: current
          }, ctx.from.id) +
          '\n\n' + (settings && settings.channel_verification ? ctx.t('channel_required', {}, ctx.from.id) : '')
        );
      } catch (e) {
        // user may have blocked bot
      }
    }
  });
}

module.exports = { handleMessages };
