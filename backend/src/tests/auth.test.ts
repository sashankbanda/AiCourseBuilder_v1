import request from 'supertest';
import app from '../app';
import pool from '../config/db';

describe('Auth Endpoints', () => {
    const testUser = {
        email: `test_${Date.now()}@example.com`,
        password: 'password123',
        full_name: 'Test User'
    };

    afterAll(async () => {
        // Cleanup: Delete the test user
        await pool.query('DELETE FROM users WHERE email = $1', [testUser.email]);
        await pool.end(); // Close DB connection
    });

    describe('POST /auth/register', () => {
        it('should register a new user', async () => {
            const res = await request(app)
                .post('/auth/register')
                .send(testUser);

            expect(res.status).toBe(201);
            expect(res.body).toHaveProperty('token');
            expect(res.body.email).toBe(testUser.email);
        });

        it('should not register an existing user', async () => {
            const res = await request(app)
                .post('/auth/register')
                .send(testUser);

            expect(res.status).toBe(400); // Or whatever your controller returns for duplicates
            expect(res.body.message).toBe('User already exists');
        });
    });

    describe('POST /auth/login', () => {
        it('should login with correct credentials', async () => {
            const res = await request(app)
                .post('/auth/login')
                .send({
                    email: testUser.email,
                    password: testUser.password
                });

            expect(res.status).toBe(200);
            expect(res.body).toHaveProperty('token');
        });

        it('should not login with incorrect password', async () => {
            const res = await request(app)
                .post('/auth/login')
                .send({
                    email: testUser.email,
                    password: 'wrongpassword'
                });

            expect(res.status).toBe(401);
        });
    });
});
