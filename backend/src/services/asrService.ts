import { execFile } from 'child_process';
import path from 'path';

/**
 * Calls the external Python ASR script (asr/transcribe.py) to get a transcript
 * when YouTube does not provide captions.
 *
 * Requirements on the user's machine:
 * - Python installed and available as `python` in PATH (or override via ASR_PYTHON_PATH env)
 * - ffmpeg installed and on PATH
 * - Inside the `asr` folder: `pip install -r requirements.txt`
 */

export async function transcribeWithASR(youtubeUrl: string): Promise<string> {
    const python = process.env.ASR_PYTHON_PATH || 'python';
    const scriptPath = path.resolve(__dirname, '../../asr/transcribe.py');

    return new Promise((resolve, reject) => {
        execFile(python, [scriptPath, youtubeUrl], { maxBuffer: 1024 * 1024 * 20 }, (error, stdout, stderr) => {
            if (error) {
                console.error('[ASR] Error executing transcribe.py:', error, stderr);
                return reject(error);
            }

            // The script prints lines like:
            // [0.00 → 4.52] Text...
            // ...
            // ===TRANSCRIPT===
            // full text...
            const marker = '===TRANSCRIPT===';
            const idx = stdout.lastIndexOf(marker);
            if (idx !== -1) {
                const plain = stdout.slice(idx + marker.length).trim();
                if (plain.length > 0) {
                    return resolve(plain);
                }
            }

            // Fallback: just use the whole stdout stripped of timestamp markers
            const cleaned = stdout
                .split('\n')
                .filter(line => !line.startsWith('[') && !line.startsWith('===TRANSCRIPT==='))
                .join(' ')
                .replace(/\s+/g, ' ')
                .trim();

            if (!cleaned) {
                return reject(new Error('ASR produced no transcript text'));
            }

            resolve(cleaned);
        });
    });
}

