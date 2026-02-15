import { execFile } from 'child_process';
import path from 'path';
import fs from 'fs';

const ASR_DIR = path.resolve(__dirname, '../../../asr');
const SCRIPT_PATH = path.join(ASR_DIR, 'transcribe.py');
const TRANSCRIPT_OUTPUT_FILE = path.join(ASR_DIR, 'transcript_output.txt');

function parseTranscriptFromStdout(stdout: string): string | null {
    const marker = '===TRANSCRIPT===';
    const idx = stdout.lastIndexOf(marker);
    if (idx !== -1) {
        const plain = stdout.slice(idx + marker.length).trim();
        if (plain.length > 0) return plain;
    }
    const cleaned = stdout
        .split('\n')
        .filter(line => !line.startsWith('[') && !line.startsWith('===TRANSCRIPT==='))
        .join(' ')
        .replace(/\s+/g, ' ')
        .trim();
    return cleaned || null;
}

function runTranscribeScript(youtubeUrl: string, env: NodeJS.ProcessEnv): Promise<string> {
    const venvPython = path.join(ASR_DIR, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
    const python = process.env.ASR_PYTHON_PATH || (fs.existsSync(venvPython) ? venvPython : 'python');
    return new Promise((resolve, reject) => {
        execFile(python, ['-u', SCRIPT_PATH, youtubeUrl], {
            maxBuffer: 1024 * 1024 * 20,
            env: { ...process.env, ...env },
        }, (error, stdout, stderr) => {
            if (error) {
                return reject({ error, stdout, stderr });
            }
            const text = parseTranscriptFromStdout(stdout);
            if (text) return resolve(text);
            reject(new Error('ASR produced no transcript text'));
        });
    });
}

/**
 * Get transcript via ASR script. Uses CPU by default. If first run fails (e.g. GPU crash),
 * retries with ASR_DEVICE=cpu so the backend always gets a transcript when possible.
 */
export async function transcribeWithASR(youtubeUrl: string): Promise<string> {
    try {
        return await runTranscribeScript(youtubeUrl, {});
    } catch (first: any) {
        const err = first?.error ?? first;
        const code = err?.code;
        const isCrash = code === 3221226505 || code === 3221225477 || (typeof code === 'number' && code !== 0);
        if (isCrash || code !== undefined) {
            console.warn('[ASR] First run failed (exit', code, '), retrying with CPU...');
            try {
                return await runTranscribeScript(youtubeUrl, { ASR_DEVICE: 'cpu' });
            } catch (retryErr: any) {
                if (fs.existsSync(TRANSCRIPT_OUTPUT_FILE)) {
                    const fromFile = fs.readFileSync(TRANSCRIPT_OUTPUT_FILE, 'utf-8').trim();
                    if (fromFile.length > 0) {
                        return fromFile;
                    }
                }
                throw retryErr?.error || retryErr;
            }
        }
        throw first?.error || first;
    }
}

