import request from 'supertest';
import app from '../app';

describe('API Health Check', () => {
    it('should return 200 OK and welcome message', async () => {
        const res = await request(app).get('/');
        expect(res.status).toBe(200);
        expect(res.text).toBe('API is running');
    });
});
