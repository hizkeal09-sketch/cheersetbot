/**
 * Grand Ethio Techs - Utility Helpers
 * Translations, admin checks, activity logging, formatting
 */

const { pool } = require('../database/connection');
const db = require('../services/db');
const config = require('../config/config');

const SUPER_ADMIN_IDS = (process.env.SUPER_ADMIN_IDS || '').split(',').map(id => id.trim()).filter(Boolean);

// ---------------------------------------------------------------------------
// Translations (English and Amharic)
// ---------------------------------------------------------------------------

const translations = {
  en: {
    welcome_new_member: 'Welcome {name} to {group}! You are restricted from sending messages until you directly add {target} new member(s). Progress: {current}/{target}. Remaining: {remaining}.',
    welcome_exempt: 'Welcome {name} to {group}! You are exempt from verification.',
    verification_instructions: 'To participate, you must directly add {target} new members to this group. Ask them to join and add them yourself. Current progress: {current}/{target}.',
    addition_counted: 'Great! You directly added {name}. Your progress is now {current}/{target}.',
    addition_not_counted: 'This new member could not be counted (already added before, bot account, or unattributed).',
    target_completed: 'Congratulations! You have completed the direct member addition requirement ({target}/{target}). You can now send messages.',
    channel_required: 'You must also join all required channels to participate.',
    channels_subscribed: 'Thank you for subscribing to all required channels. You are now verified!',
    verification_success: 'Verification complete! You are now unlocked and can send messages.',
    verification_status: 'Your verification status: {status}. Additions: {current}/{target}. Channels: {channelStatus}.',
    help: 'Grand Ethio Techs Bot Help:\n/start - Start the bot\n/help - Show this help\n/check - Check your verification status\n/instructions - Show verification instructions\n/language - Change language (en/am)',
    admin_only: 'This command is for administrators only.',
    not_admin: 'You are not an administrator of this group.',
    super_admin_only: 'This command is for super administrators only.',
    target_set: 'Direct addition target set to {target} for this group.',
    target_current: 'Current direct addition target: {target}.',
    channel_mode_enabled: 'Channel subscription verification is now ENABLED for this group.',
    channel_mode_disabled: 'Channel subscription verification is now DISABLED for this group.',
    channel_added: 'Required channel added: {channel}.',
    channel_removed: 'Required channel removed: {channel}.',
    channel_list: 'Required channels for this group: {channels}',
    channel_list_empty: 'No required channels configured.',
    verify_member: 'Manual verification for user {user} completed.',
    exempt_added: 'User {user} is now exempt from verification.',
    exempt_removed: 'User {user} is no longer exempt.',
    count_set: 'Manual count for user {user} set to {count}.',
    count_reset: 'Count for user {user} reset to 0.',
    stats_title: 'Group Statistics for {group}',
    stats_total_additions: 'Total direct additions: {count}',
    stats_verified: 'Verified members: {count}',
    stats_pending: 'Pending verification: {count}',
    stats_channels: 'Required channels: {count}',
    leaderboard_title: 'Leaderboard - Top Direct Member Adders',
    leaderboard_entry: '#{rank}. {name} - {count} additions',
    leaderboard_empty: 'No additions recorded yet.',
    error_occurred: 'An error occurred. Please try again later.',
    database_error: 'Database error. Please try again later.',
    language_set: 'Language set to {lang}.',
    language_current: 'Current language: {lang}',
    already_verified: 'You are already verified and can send messages.',
    already_exempt: 'You are already exempt from verification.',
    not_exempt: 'You are not exempt from verification.',
    member_not_found: 'Member not found in this group.',
    invalid_target: 'Invalid target number. Please provide a positive number.',
    broadcast_sent: 'Broadcast sent to {count} recipients.',
    bot_added: 'Grand Ethio Techs Bot has been added to {group}! Use /admin to configure.',
    bot_removed: 'Grand Ethio Techs Bot has been removed from {group}.',
    permission_needed: 'I need administrator permissions with the ability to restrict members to work properly.',
    welcome_enabled: 'Welcome messages are now ENABLED.',
    welcome_disabled: 'Welcome messages are now DISABLED.',
    warning_added: 'Warning added to {user}. Total warnings: {count}/{limit}.',
    warning_limit: '{user} has reached the warning limit and will be muted.',
    unmuted: '{user} has been unmuted.',
    banned: '{user} has been banned.',
    unbanned: '{user} has been unbanned.',
    bot_removed_admin: 'Unwanted bot removed: {bot}.',
    settings_title: 'Group Settings',
    settings_target: 'Target additions: {target}',
    settings_channel_mode: 'Channel verification: {mode}',
    settings_language: 'Language: {lang}',
    settings_anti_spam: 'Anti-spam: {status}',
    settings_warning_limit: 'Warning limit: {limit}',
    admin_dashboard: 'Grand Ethio Techs Administrator Dashboard',
    admin_menu_stats: 'Statistics',
    admin_menu_channels: 'Manage Channels',
    admin_menu_settings: 'Settings',
    admin_menu_leaderboard: 'Leaderboard',
    admin_menu_moderation: 'Moderation',
    admin_menu_welcome: 'Welcome Message',
    admin_menu_exempt: 'Manage Exemptions',
    admin_menu_activity: 'Activity Logs',
    back_to_menu: 'Back to Menu',
    confirm_action: 'Are you sure you want to perform this action?',
    action_cancelled: 'Action cancelled.',
    action_completed: 'Action completed successfully.'
  },
  am: {
    welcome_new_member: '{group}-n {name}-n misalech! Hulu yetemadachew new {target} aydelem wedaj. Progress: {current}/{target}. Remaining: {remaining}.',
    welcome_exempt: '{group}-n {name}-n misalech! Verification-m hulu neger.',
    verification_instructions: 'Yetemadel betemada, {target} hos aydelem wedaj. Progress: {current}/{target}.',
    addition_counted: 'Gize! {name}-n direct wedajeshew. Progress {current}/{target}.',
    target_completed: 'Ameseginalehu! Direct member addition requirement ({target}/{target}) tadessewalew. Now mesage yegizeyall.',
    channel_required: 'Yetemada group channel-ochu yetehudalew.',
    verification_success: 'Verification tadessewalew! Mesage yegizeyall.',
    help: 'Grand Ethio Techs Bot Help:\n/start - Bot yemeder\n/help - Help yemeder\n/check - Verification status\n/instructions - Instructions',
    admin_only: 'Admin-ochu yedemin command.',
    not_admin: 'Admin ayehun.',
    super_admin_only: 'Super admin-ochu yedemin command.',
    target_set: 'Direct addition target {target} set.',
    target_current: 'Current target: {target}.',
    channel_mode_enabled: 'Channel verification enabled.',
    channel_mode_disabled: 'Channel verification disabled.',
    channel_added: 'Channel added: {channel}.',
    channel_removed: 'Channel removed: {channel}.',
    channel_list: 'Channels: {channels}',
    channel_list_empty: 'No channels configured.',
    verify_member: 'Verification done for {user}.',
    exempt_added: '{user} exempt neger.',
    exempt_removed: '{user} exempt aydel.',
    count_set: 'Count for {user} set to {count}.',
    count_reset: 'Count for {user} reset to 0.',
    stats_title: '{group} Statistics',
    stats_total_additions: 'Total additions: {count}',
    stats_verified: 'Verified: {count}',
    stats_pending: 'Pending: {count}',
    stats_channels: 'Required channels: {count}',
    leaderboard_title: 'Leaderboard - Top Adders',
    leaderboard_entry: '#{rank}. {name} - {count}',
    leaderboard_empty: 'No additions yet.',
    error_occurred: 'Error yalew. Yetemachaw.',
    database_error: 'Database error.',
    language_set: 'Language set to {lang}.',
    language_current: 'Current language: {lang}',
    already_verified: 'Already verified.',
    already_exempt: 'Already exempt.',
    not_exempt: 'Not exempt.',
    member_not_found: 'Member not found.',
    invalid_target: 'Invalid target number.',
    broadcast_sent: 'Broadcast sent to {count}.',
    bot_added: 'Bot added to {group}! /admin yemeder.',
    bot_removed: 'Bot removed from {group}.',
    permission_needed: 'Admin permission needed.',
    welcome_enabled: 'Welcome messages enabled.',
    welcome_disabled: 'Welcome messages disabled.',
    warning_added: 'Warning added to {user}. {count}/{limit}.',
    warning_limit: '{user} warning limit reached, will be muted.',
    unmuted: '{user} unmuted.',
    banned: '{user} banned.',
    unbanned: '{user} unbanned.',
    bot_removed_admin: 'Unwanted bot removed: {bot}.',
    settings_title: 'Group Settings',
    settings_target: 'Target additions: {target}',
    settings_channel_mode: 'Channel verification: {mode}',
    settings_language: 'Language: {lang}',
    settings_anti_spam: 'Anti-spam: {status}',
    settings_warning_limit: 'Warning limit: {limit}',
    admin_dashboard: 'Grand Ethio Techs Admin Dashboard',
    admin_menu_stats: 'Statistics',
    admin_menu_channels: 'Manage Channels',
    admin_menu_settings: 'Settings',
    admin_menu_leaderboard: 'Leaderboard',
    admin_menu_moderation: 'Moderation',
    admin_menu_welcome: 'Welcome Message',
    admin_menu_exempt: 'Manage Exemptions',
    admin_menu_activity: 'Activity Logs',
    back_to_menu: 'Back to Menu',
    confirm_action: 'Are you sure?',
    action_cancelled: 'Action cancelled.',
    action_completed: 'Action completed.'
  }
};

// ---------------------------------------------------------------------------
// Translation helper
// ---------------------------------------------------------------------------

function t(key, vars, userId) {
  let lang = 'en';
  if (userId) {
    const user = dbGetUserLang(userId);
    if (user) lang = user;
  }
  const dict = translations[lang] || translations.en;
  let text = dict[key] || translations.en[key] || key;
  if (vars) {
    Object.keys(vars).forEach(k => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), vars[k]);
    });
  }
  return text;
}

async function dbGetUserLang(userId) {
  try {
    const { pool } = require('../database/connection');
    const result = await pool.query('SELECT language_code FROM users WHERE telegram_id = $1', [userId]);
    if (result.rows.length > 0) return result.rows[0].language_code;
  } catch (e) {
    // ignore
  }
  return null;
}

// ---------------------------------------------------------------------------
// Get user language
// ---------------------------------------------------------------------------

async function getUserLang(userId) {
  if (!userId) return 'en';
  try {
    const { pool } = require('../database/connection');
    const result = await pool.query('SELECT language_code FROM users WHERE telegram_id = $1', [userId]);
    if (result.rows.length > 0) return result.rows[0].language_code;
  } catch (e) {
    // ignore
  }
  return 'en';
}

// ---------------------------------------------------------------------------
// Admin checks
// ---------------------------------------------------------------------------

function isSuperAdmin(userId) {
  return SUPER_ADMIN_IDS.includes(String(userId));
}

async function isAdmin(userId, groupTelegramId) {
  if (!userId) return false;
  if (isSuperAdmin(userId)) return true;
  if (!groupTelegramId) return false;
  try {
    const group = await db.getGroupByTelegramId(groupTelegramId);
    if (!group) return false;
    const admins = await db.getAdmins(group.id);
    return admins.some(a => a.user_telegram_id == userId);
  } catch (e) {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Format user name
// ---------------------------------------------------------------------------

function formatUserName(user) {
  if (!user) return 'Unknown';
  const parts = [user.first_name, user.last_name].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : (user.username || `User ${user.id}`);
}

// ---------------------------------------------------------------------------
// Format member mention
// ---------------------------------------------------------------------------

function formatMention(user) {
  const name = formatUserName(user);
  if (user.username) return `@${user.username}`;
  return `[${name}](tg://user?id=${user.id})`;
}

// ---------------------------------------------------------------------------
// Check required additions remaining
// ---------------------------------------------------------------------------

async function getRemainingAdditions(groupId, userTelegramId) {
  const settings = await db.getGroupSettings(groupId);
  const target = settings ? settings.target_additions : config.defaultTargetAdditions;
  const current = await db.getAdditionCount(groupId, userTelegramId);
  return Math.max(0, target - current);
}

// ---------------------------------------------------------------------------
// Check if verification complete
// ---------------------------------------------------------------------------

async function isVerificationComplete(groupId, userTelegramId) {
  const verification = await db.getVerification(groupId, userTelegramId);
  if (!verification) return false;
  const settings = await db.getGroupSettings(groupId);
  const additionsDone = verification.additions_completed;
  const channelsDone = verification.channels_subscribed;
  const channelVerificationEnabled = settings ? settings.channel_verification : false;
  if (channelVerificationEnabled) {
    return additionsDone && channelsDone;
  }
  return additionsDone;
}

// ---------------------------------------------------------------------------
// Log activity
// ---------------------------------------------------------------------------

async function logActivity(groupId, userTelegramId, action, details) {
  return db.logActivity(groupId, userTelegramId, action, details);
}

module.exports = {
  t,
  getUserLang,
  isAdmin,
  isSuperAdmin,
  formatUserName,
  formatMention,
  getRemainingAdditions,
  isVerificationComplete,
  logActivity,
  translations,
  SUPER_ADMIN_IDS
};
