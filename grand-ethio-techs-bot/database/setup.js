/**
 * Grand Ethio Techs - Database Setup Script
 * Run once to create all required tables.
 * Usage: node database/setup.js
 */

const { pool } = require('./connection');

const createTables = `
-- 1. users table - stores all bot users
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  username VARCHAR(255),
  first_name VARCHAR(255),
  last_name VARCHAR(255),
  language_code VARCHAR(10) DEFAULT 'en',
  is_bot BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. groups table - stores registered groups
CREATE TABLE IF NOT EXISTS groups (
  id SERIAL PRIMARY KEY,
  telegram_id BIGINT UNIQUE NOT NULL,
  title VARCHAR(255),
  type VARCHAR(50) DEFAULT 'supergroup',
  username VARCHAR(255),
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. group_settings table - per-group configuration
CREATE TABLE IF NOT EXISTS group_settings (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  target_additions INTEGER DEFAULT 5 NOT NULL,
  channel_verification BOOLEAN DEFAULT FALSE NOT NULL,
  welcome_message TEXT,
  welcome_enabled BOOLEAN DEFAULT TRUE NOT NULL,
  language VARCHAR(10) DEFAULT 'en',
  anti_spam BOOLEAN DEFAULT TRUE NOT NULL,
  link_restrictions BOOLEAN DEFAULT FALSE NOT NULL,
  warning_limit INTEGER DEFAULT 3 NOT NULL,
  mute_duration_seconds INTEGER DEFAULT 3600 NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id)
);

-- 4. member_additions table - records every successful direct addition
CREATE TABLE IF NOT EXISTS member_additions (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  inviter_telegram_id BIGINT NOT NULL,
  added_member_telegram_id BIGINT NOT NULL,
  added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  is_valid BOOLEAN DEFAULT TRUE NOT NULL,
  source_event VARCHAR(100) DEFAULT 'new_chat_members',
  UNIQUE(group_id, inviter_telegram_id, added_member_telegram_id)
);

-- 5. verifications table - tracks member verification status
CREATE TABLE IF NOT EXISTS verifications (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  user_telegram_id BIGINT NOT NULL,
  additions_completed BOOLEAN DEFAULT FALSE NOT NULL,
  channels_subscribed BOOLEAN DEFAULT TRUE NOT NULL,
  verified BOOLEAN DEFAULT FALSE NOT NULL,
  verified_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, user_telegram_id)
);

-- 6. channels table - required channels per group
CREATE TABLE IF NOT EXISTS channels (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  channel_id VARCHAR(255) NOT NULL,
  channel_username VARCHAR(255),
  channel_title VARCHAR(255),
  is_required BOOLEAN DEFAULT TRUE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, channel_id)
);

-- 7. exemptions table - exempted members
CREATE TABLE IF NOT EXISTS exemptions (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  user_telegram_id BIGINT NOT NULL,
  reason TEXT,
  exempted_by BIGINT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, user_telegram_id)
);

-- 8. admins table - group administrators
CREATE TABLE IF NOT EXISTS admins (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  user_telegram_id BIGINT NOT NULL,
  role VARCHAR(50) DEFAULT 'admin',
  added_by BIGINT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(group_id, user_telegram_id)
);

-- 9. warnings table - member warning system
CREATE TABLE IF NOT EXISTS warnings (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  user_telegram_id BIGINT NOT NULL,
  warned_by BIGINT,
  reason TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. campaigns table - broadcast campaigns
CREATE TABLE IF NOT EXISTS campaigns (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  message_text TEXT NOT NULL,
  sent_by BIGINT,
  sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  recipient_count INTEGER DEFAULT 0
);

-- 11. activity_logs table - audit log
CREATE TABLE IF NOT EXISTS activity_logs (
  id SERIAL PRIMARY KEY,
  group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
  user_telegram_id BIGINT,
  action VARCHAR(255) NOT NULL,
  details TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_member_additions_group ON member_additions(group_id);
CREATE INDEX IF NOT EXISTS idx_member_additions_inviter ON member_additions(inviter_telegram_id);
CREATE INDEX IF NOT EXISTS idx_verifications_group ON verifications(group_id);
CREATE INDEX IF NOT EXISTS idx_warnings_group_user ON warnings(group_id, user_telegram_id);

console.log('All tables created successfully.');
process.exit(0);
`;

pool.query(createTables)
  .then(() => {
    console.log('Database setup completed.');
  })
  .catch((err) => {
    console.error('Database setup failed:', err);
    process.exit(1);
  });
