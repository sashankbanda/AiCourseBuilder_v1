import { Pool } from 'pg';
import dotenv from 'dotenv';
import path from 'path';

dotenv.config({ path: path.resolve(__dirname, '../../../.env') });

const connectionString = process.env.DATABASE_URL;

// Decide how to connect:
// - If DATABASE_URL is set and points to localhost, use it without SSL (local Postgres)
// - If DATABASE_URL is set and points to a remote host, add SSL (for cloud DBs like Neon)
// - Otherwise, fall back to individual DB_* env vars with local defaults

let pool: Pool;

if (connectionString) {
    const isLocal = /localhost|127\.0\.0\.1/i.test(connectionString);

    pool = new Pool(
        isLocal
            ? { connectionString }
            : {
                  connectionString,
                  ssl: {
                      rejectUnauthorized: false,
                  },
              }
    );
} else {
    pool = new Pool({
        user: process.env.DB_USER || 'postgres',
        host: process.env.DB_HOST || 'localhost',
        database: process.env.DB_NAME || 'aicoursebuilder',
        password: process.env.DB_PASSWORD || 'postgres',
        port: parseInt(process.env.DB_PORT || '5432', 10),
    });
}

pool.on('error', (err) => {
    console.error('Unexpected error on idle client', err);
    process.exit(-1);
});

export const query = (text: string, params?: any[]) => pool.query(text, params);

export default pool;
