import { render, screen } from '@testing-library/react';
import App from './App';
import { describe, it, expect } from 'vitest';

describe('App Component', () => {
    it('renders sign in screen by default', () => {
        render(<App />);
        const heading = screen.getByText(/AI Course Builder/i);
        expect(heading).toBeInTheDocument();

        const subtext = screen.getByText(/Sign in to start learning/i);
        expect(subtext).toBeInTheDocument();
    });
});
