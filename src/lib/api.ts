const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

const getHeaders = () => {
    const token = localStorage.getItem('token');
    return {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
};

export const api = {
    get: async (endpoint: string) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            headers: getHeaders(),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'API Error');
        return data;
    },

    post: async (endpoint: string, body: any) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'API Error');
        return data;
    },

    put: async (endpoint: string, body: any) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'API Error');
        return data;
    },

    delete: async (endpoint: string) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            method: 'DELETE',
            headers: getHeaders(),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.message || 'API Error');
        return data;
    },

    postStream: async (endpoint: string, body: any, onEvent: (event: string, data: any) => void) => {
        const res = await fetch(`${API_URL}${endpoint}`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(body),
        });

        if (!res.ok) {
            const errorText = await res.text();
            console.error('Stream request failed. Status:', res.status, 'Raw body:', errorText);
            try {
                const errJson = JSON.parse(errorText);
                throw new Error(errJson.message || 'Stream Error');
            } catch (e) {
                // If parsing fails, throw the raw text directly
                // (This catches "Unexpected token" errors)
                throw new Error(errorText || `Stream Error: ${res.status}`);
            }
        }

        const reader = res.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) throw new Error('No readable stream');

        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');

            // Keep the last partial event in the buffer
            buffer = events.pop() || '';

            for (const eventBlock of events) {
                if (!eventBlock.trim()) continue;

                const eventMatch = eventBlock.match(/event: (.*)/);
                const dataMatch = eventBlock.match(/data: (.*)/);

                if (eventMatch && dataMatch) {
                    const event = eventMatch[1];
                    try {
                        const data = JSON.parse(dataMatch[1]);
                        onEvent(event, data);
                    } catch (e) {
                        console.warn('Stream parse error. Raw data:', dataMatch[1]);
                        // If it looks like a plain string error, wrap it
                        onEvent(event, { message: dataMatch[1] });
                    }
                }
            }
        }
    }
};
