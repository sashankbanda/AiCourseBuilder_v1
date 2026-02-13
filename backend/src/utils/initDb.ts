import { Client } from 'pg';
import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';

dotenv.config({ path: path.join(__dirname, '../../../.env') });

const setup = async () => {
    // Prefer DATABASE_URL if present
    const connectionString = process.env.DATABASE_URL;

    if (!connectionString) {
        console.error('DATABASE_URL not found in .env (expected for local Postgres).');
        process.exit(1);
    }

    console.log('Connecting to database to apply schema...');

    const isLocal = /localhost|127\.0\.0\.1/i.test(connectionString);

    const client = new Client(
        isLocal
            ? { connectionString }
            : {
                  connectionString,
                  ssl: {
                      rejectUnauthorized: false,
                  },
              }
    );

    try {
        await client.connect();

        console.log('Applying schema...');
        const schemaPath = path.join(__dirname, '../../schema.sql');
        const schemaSql = fs.readFileSync(schemaPath, 'utf8');

        await client.query(schemaSql);
        console.log('Schema applied successfully.');
        await client.end();
    } catch (err) {
        console.error('Database setup failed:', err);
        process.exit(1);
    }
};

setup();
