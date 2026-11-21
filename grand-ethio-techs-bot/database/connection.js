/**
 * Grand Ethio Techs - Database Connection
 * Neon PostgreSQL connection pool
 */

const { Pool } = require('pg');

// Create connection pool from environment variable
const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
  max: 10,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000,
});

// Test the connection on startup
pool.on('connect', () => {
  console.log('Connected to Neon PostgreSQL database');
});

pool.on('error', (err) => {
  console.error('Unexpected database pool error:', err);
});

module.exports = { pool };
