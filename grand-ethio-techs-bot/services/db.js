/**
 * Grand Ethio Techs - Database Service Layer
 * All database operations for the bot
 */

const { pool } = require('../database/connection');

// ===========================================================================
// USERS
// ===========================================================================

async function upsertUser(telegramUser) {
  if (!telegramUser) return null;
  const { id, username, first_name, last_name, is_bot, language_code } = telegramUser;
  const query = `
    INSERT INTO users (telegram_id, username, first_name, last_name, is_bot, language_code, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
      username = EXCLUDED.username,
      first_name = EXCLUDED.first_name,
      last_name = EXCLUDED.last_name,
      is_bot = EXCLUDED.is_bot,
      language_code = COALESCE(users.language_code, EXCLUDED.language_code),
      updated_at = CURRENT_TIMESTAMP
    RETURNING id, telegram_id, username, first_name, last_name, language_code, is_bot
  `;
  const values = [id, username || null, first_name || null, last_name || null, !!is_bot, language_code || 'en'];
  const result = await pool.query(query, values);
  return result.rows[0];
}

async function getUserByTelegramId(telegramId) {
  const query = 'SELECT * FROM users WHERE telegram_id = $1';
  const result = await pool.query(query, [telegramId]);
  return result.rows[0] || null;
}

async function setUserLanguage(telegramId, lang) {
  const query = `
    UPDATE users SET language_code = $1, updated_at = CURRENT_TIMESTAMP
    WHERE telegram_id = $2
    RETURNING *
  `;
  const result = await pool.query(query, [lang, telegramId]);
  return result.rows[0] || null;
}

// ===========================================================================
// GROUPS
// ===========================================================================

async function upsertGroup(chat) {
  const query = `
    INSERT INTO groups (telegram_id, title, type, username, updated_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    ON CONFLICT (telegram_id)
    DO UPDATE SET
      title = EXCLUDED.title,
      type = EXCLUDED.type,
      username = EXCLUDED.username,
      updated_at = CURRENT_TIMESTAMP
    RETURNING id, telegram_id, title, type, username, is_active
  `;
  const values = [chat.id, chat.title || null, chat.type, chat.username || null];
  const result = await pool.query(query, values);
  return result.rows[0];
}

async function ensureGroup(chat) {
  if (!chat || (chat.type !== 'group' && chat.type !== 'supergroup')) return null;
  await upsertGroup(chat);
  await ensureGroupSettings(chat.id);
  return true;
}

async function getGroupByTelegramId(telegramId) {
  const query = 'SELECT * FROM groups WHERE telegram_id = $1';
  const result = await pool.query(query, [telegramId]);
  return result.rows[0] || null;
}

async function getAllActiveGroups() {
  const query = 'SELECT * FROM groups WHERE is_active = TRUE ORDER BY id';
  const result = await pool.query(query);
  return result.rows;
}

// ===========================================================================
// GROUP SETTINGS
// ===========================================================================

async function ensureGroupSettings(telegramGroupId) {
  const group = await getGroupByTelegramId(telegramGroupId);
  if (!group) return null;
  const existing = await getGroupSettings(group.id);
  if (existing) return existing;
  const query = `
    INSERT INTO group_settings (group_id, updated_at)
    VALUES ($1, CURRENT_TIMESTAMP)
    RETURNING *
  `;
  const result = await pool.query(query, [group.id]);
  return result.rows[0];
}

async function getGroupSettings(groupId) {
  const query = 'SELECT * FROM group_settings WHERE group_id = $1';
  const result = await pool.query(query, [groupId]);
  return result.rows[0] || null;
}

async function updateGroupSetting(groupId, field, value) {
  const query = `
    UPDATE group_settings
    SET ${field} = $2, updated_at = CURRENT_TIMESTAMP
    WHERE group_id = $1
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, value]);
  return result.rows[0] || null;
}

async function setTargetAdditions(groupId, target) {
  return updateGroupSetting(groupId, 'target_additions', parseInt(target, 10));
}

async function toggleChannelVerification(groupId, enabled) {
  return updateGroupSetting(groupId, 'channel_verification', !!enabled);
}

// ===========================================================================
// MEMBER ADDITIONS (permanent counting)
// ===========================================================================

async function recordMemberAddition(groupId, inviterTelegramId, addedMemberTelegramId, sourceEvent = 'new_chat_members') {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const query = `
      INSERT INTO member_additions (group_id, inviter_telegram_id, added_member_telegram_id, source_event, is_valid)
      VALUES ($1, $2, $3, $4, TRUE)
      ON CONFLICT (group_id, inviter_telegram_id, added_member_telegram_id)
      DO NOTHING
      RETURNING id
    `;
    const result = await client.query(query, [groupId, inviterTelegramId, addedMemberTelegramId, sourceEvent]);
    await client.query('COMMIT');
    return result.rows.length > 0;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

async function getAdditionCount(groupId, inviterTelegramId) {
  const query = `
    SELECT COUNT(*) AS count
    FROM member_additions
    WHERE group_id = $1 AND inviter_telegram_id = $2 AND is_valid = TRUE
  `;
  const result = await pool.query(query, [groupId, inviterTelegramId]);
  return parseInt(result.rows[0].count, 10);
}

async function getAdditionCountForUser(groupId, userTelegramId) {
  return getAdditionCount(groupId, userTelegramId);
}

async function getAdditionsByInviter(groupId, inviterTelegramId, limit = 50) {
  const query = `
    SELECT ma.*, u.username, u.first_name
    FROM member_additions ma
    LEFT JOIN users u ON u.telegram_id = ma.added_member_telegram_id
    WHERE ma.group_id = $1 AND ma.inviter_telegram_id = $2 AND ma.is_valid = TRUE
    ORDER BY ma.added_at DESC
    LIMIT $3
  `;
  const result = await pool.query(query, [groupId, inviterTelegramId, limit]);
  return result.rows;
}

async function getAllAdditionsCount(groupId) {
  const query = `
    SELECT COUNT(*) AS count
    FROM member_additions
    WHERE group_id = $1 AND is_valid = TRUE
  `;
  const result = await pool.query(query, [groupId]);
  return parseInt(result.rows[0].count, 10);
}

async function getLeaderboard(groupId, limit = 10) {
  const query = `
    SELECT inviter_telegram_id AS user_id, COUNT(*) AS additions
    FROM member_additions
    WHERE group_id = $1 AND is_valid = TRUE
    GROUP BY inviter_telegram_id
    ORDER BY additions DESC
    LIMIT $2
  `;
  const result = await pool.query(query, [groupId, limit]);
  return result.rows;
}

async function setManualCount(groupId, userTelegramId, newCount, adjustedBy) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('DELETE FROM member_additions WHERE group_id = $1 AND inviter_telegram_id = $2', [groupId, userTelegramId]);
    for (let i = 0; i < newCount; i++) {
      await client.query(
        `INSERT INTO member_additions (group_id, inviter_telegram_id, added_member_telegram_id, source_event, is_valid)
         VALUES ($1, $2, $3, 'manual_adjustment', TRUE)
         ON CONFLICT DO NOTHING`,
        [groupId, userTelegramId, 0]
      );
    }
    await logActivityClient(client, groupId, adjustedBy, 'set_count', `Set count for user ${userTelegramId} to ${newCount}`);
    await client.query('COMMIT');
    return true;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

async function resetCount(groupId, userTelegramId, resetBy) {
  return setManualCount(groupId, userTelegramId, 0, resetBy);
}

// ===========================================================================
// VERIFICATIONS
// ===========================================================================

async function ensureVerification(groupId, userTelegramId) {
  const existing = await getVerification(groupId, userTelegramId);
  if (existing) return existing;
  const query = `
    INSERT INTO verifications (group_id, user_telegram_id, created_at, updated_at)
    VALUES ($1, $2, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, userTelegramId]);
  return result.rows[0];
}

async function getVerification(groupId, userTelegramId) {
  const query = 'SELECT * FROM verifications WHERE group_id = $1 AND user_telegram_id = $2';
  const result = await pool.query(query, [groupId, userTelegramId]);
  return result.rows[0] || null;
}

async function updateVerificationStatus(groupId, userTelegramId, fields) {
  const setParts = [];
  const values = [groupId, userTelegramId];
  let idx = 3;
  for (const [key, val] of Object.entries(fields)) {
    setParts.push(`${key} = $${idx++}`);
    values.push(val);
  }
  setParts.push(`updated_at = CURRENT_TIMESTAMP`);
  if (fields.verified === true) {
    setParts.push(`verified_at = CURRENT_TIMESTAMP`);
  }
  const query = `
    UPDATE verifications
    SET ${setParts.join(', ')}
    WHERE group_id = $1 AND user_telegram_id = $2
    RETURNING *
  `;
  const result = await pool.query(query, values);
  return result.rows[0] || null;
}

async function setAdditionsCompleted(groupId, userTelegramId, completed) {
  return updateVerificationStatus(groupId, userTelegramId, { additions_completed: completed });
}

async function setChannelsSubscribed(groupId, userTelegramId, subscribed) {
  return updateVerificationStatus(groupId, userTelegramId, { channels_subscribed: subscribed });
}

async function setVerified(groupId, userTelegramId, verified) {
  return updateVerificationStatus(groupId, userTelegramId, { verified });
}

async function getPendingVerifications(groupId) {
  const query = `
    SELECT v.*, u.username, u.first_name
    FROM verifications v
    LEFT JOIN users u ON u.telegram_id = v.user_telegram_id
    WHERE v.group_id = $1 AND v.verified = FALSE
    ORDER BY v.created_at ASC
  `;
  const result = await pool.query(query, [groupId]);
  return result.rows;
}

async function getVerificationStats(groupId) {
  const query = `
    SELECT
      COUNT(*) AS total,
      SUM(CASE WHEN verified THEN 1 ELSE 0 END) AS verified,
      SUM(CASE WHEN NOT verified THEN 1 ELSE 0 END) AS pending
    FROM verifications
    WHERE group_id = $1
  `;
  const result = await pool.query(query, [groupId]);
  return result.rows[0];
}

// ===========================================================================
// CHANNELS
// ===========================================================================

async function addChannel(groupId, channelId, channelUsername, channelTitle) {
  const query = `
    INSERT INTO channels (group_id, channel_id, channel_username, channel_title, created_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    ON CONFLICT (group_id, channel_id)
    DO UPDATE SET
      channel_username = EXCLUDED.channel_username,
      channel_title = EXCLUDED.channel_title,
      created_at = CURRENT_TIMESTAMP
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, channelId, channelUsername || null, channelTitle || null]);
  return result.rows[0];
}

async function getChannels(groupId) {
  const query = 'SELECT * FROM channels WHERE group_id = $1 AND is_required = TRUE ORDER BY id';
  const result = await pool.query(query, [groupId]);
  return result.rows;
}

async function removeChannel(groupId, channelId) {
  const query = 'DELETE FROM channels WHERE group_id = $1 AND channel_id = $2 RETURNING *';
  const result = await pool.query(query, [groupId, channelId]);
  return result.rows[0] || null;
}

// ===========================================================================
// EXEMPTIONS
// ===========================================================================

async function addExemption(groupId, userTelegramId, reason, exemptedBy) {
  const query = `
    INSERT INTO exemptions (group_id, user_telegram_id, reason, exempted_by, created_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    ON CONFLICT (group_id, user_telegram_id)
    DO UPDATE SET reason = EXCLUDED.reason, exempted_by = EXCLUDED.exempted_by, created_at = CURRENT_TIMESTAMP
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, userTelegramId, reason || null, exemptedBy || null]);
  return result.rows[0];
}

async function removeExemption(groupId, userTelegramId) {
  const query = 'DELETE FROM exemptions WHERE group_id = $1 AND user_telegram_id = $2 RETURNING *';
  const result = await pool.query(query, [groupId, userTelegramId]);
  return result.rows[0] || null;
}

async function getExemptions(groupId) {
  const query = 'SELECT * FROM exemptions WHERE group_id = $1 ORDER BY created_at DESC';
  const result = await pool.query(query, [groupId]);
  return result.rows;
}

async function isExempt(groupId, userTelegramId) {
  const query = 'SELECT 1 FROM exemptions WHERE group_id = $1 AND user_telegram_id = $2';
  const result = await pool.query(query, [groupId, userTelegramId]);
  return result.rows.length > 0;
}

// ===========================================================================
// ADMINS
// ===========================================================================

async function addAdmin(groupId, userTelegramId, role, addedBy) {
  const query = `
    INSERT INTO admins (group_id, user_telegram_id, role, added_by, created_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    ON CONFLICT (group_id, user_telegram_id)
    DO UPDATE SET role = EXCLUDED.role
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, userTelegramId, role || 'admin', addedBy || null]);
  return result.rows[0];
}

async function getAdmins(groupId) {
  const query = 'SELECT * FROM admins WHERE group_id = $1 ORDER BY created_at DESC';
  const result = await pool.query(query, [groupId]);
  return result.rows;
}

// ===========================================================================
// WARNINGS
// ===========================================================================

async function addWarning(groupId, userTelegramId, warnedBy, reason) {
  const query = `
    INSERT INTO warnings (group_id, user_telegram_id, warned_by, reason, created_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, userTelegramId, warnedBy || null, reason || null]);
  return result.rows[0];
}

async function getWarnings(groupId, userTelegramId) {
  const query = 'SELECT * FROM warnings WHERE group_id = $1 AND user_telegram_id = $2 ORDER BY created_at DESC';
  const result = await pool.query(query, [groupId, userTelegramId]);
  return result.rows;
}

async function getWarningCount(groupId, userTelegramId) {
  const query = 'SELECT COUNT(*) AS count FROM warnings WHERE group_id = $1 AND user_telegram_id = $2';
  const result = await pool.query(query, [groupId, userTelegramId]);
  return parseInt(result.rows[0].count, 10);
}

async function clearWarnings(groupId, userTelegramId) {
  const query = 'DELETE FROM warnings WHERE group_id = $1 AND user_telegram_id = $2 RETURNING *';
  const result = await pool.query(query, [groupId, userTelegramId]);
  return result.rows;
}

// ===========================================================================
// ACTIVITY LOGS
// ===========================================================================

async function logActivity(groupId, userTelegramId, action, details) {
  const query = `
    INSERT INTO activity_logs (group_id, user_telegram_id, action, details, created_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    RETURNING *
  `;
  const result = await pool.query(query, [groupId, userTelegramId || null, action, details || null]);
  return result.rows[0];
}

async function logActivityClient(client, groupId, userTelegramId, action, details) {
  const query = `
    INSERT INTO activity_logs (group_id, user_telegram_id, action, details, created_at)
    VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
    RETURNING *
  `;
  const result = await client.query(query, [groupId, userTelegramId || null, action, details || null]);
  return result.rows[0];
}

async function getActivityLogs(groupId, limit = 50) {
  const query = `
    SELECT al.*, u.username, u.first_name
    FROM activity_logs al
    LEFT JOIN users u ON u.telegram_id = al.user_telegram_id
    WHERE al.group_id = $1
    ORDER BY al.created_at DESC
    LIMIT $2
  `;
  const result = await pool.query(query, [groupId, limit]);
  return result.rows;
}

// ===========================================================================
// STATS
// ===========================================================================

async function getGroupStats(groupId) {
  const totalAdditions = await getAllAdditionsCount(groupId);
  const verificationStats = await getVerificationStats(groupId);
  const channels = await getChannels(groupId);
  const exemptions = await getExemptions(groupId);
  return {
    totalAdditions,
    totalMembers: verificationStats.total || 0,
    verifiedMembers: verificationStats.verified || 0,
    pendingMembers: verificationStats.pending || 0,
    requiredChannels: channels.length,
    exemptedMembers: exemptions.length
  };
}

module.exports = {
  upsertUser,
  getUserByTelegramId,
  setUserLanguage,
  upsertGroup,
  ensureGroup,
  getGroupByTelegramId,
  getAllActiveGroups,
  ensureGroupSettings,
  getGroupSettings,
  updateGroupSetting,
  setTargetAdditions,
  toggleChannelVerification,
  recordMemberAddition,
  getAdditionCount,
  getAdditionCountForUser,
  getAdditionsByInviter,
  getAllAdditionsCount,
  getLeaderboard,
  setManualCount,
  resetCount,
  ensureVerification,
  getVerification,
  updateVerificationStatus,
  setAdditionsCompleted,
  setChannelsSubscribed,
  setVerified,
  getPendingVerifications,
  getVerificationStats,
  addChannel,
  getChannels,
  removeChannel,
  addExemption,
  removeExemption,
  getExemptions,
  isExempt,
  addAdmin,
  getAdmins,
  addWarning,
  getWarnings,
  getWarningCount,
  clearWarnings,
  logActivity,
  logActivityClient,
  getActivityLogs,
  getGroupStats
};
