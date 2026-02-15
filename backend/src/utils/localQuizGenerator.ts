/**
 * Local quiz generator (no Gemini/LLM).
 * - Extracts key sentences and terms from course content (TF-based, like NER/keywords).
 * - Builds MCQs: question from sentence, correct answer = key term, distractors = other key terms.
 * - Difficulty maps to Bloom-style count and question style (remember → analyze).
 */

const STOPWORDS = new Set([
    'the', 'and', 'a', 'an', 'to', 'of', 'in', 'on', 'for', 'with', 'at', 'by',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those',
    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'them', 'his', 'her', 'their',
    'as', 'from', 'or', 'but', 'if', 'then', 'so', 'because',
    'can', 'could', 'should', 'would', 'may', 'might',
    'not', 'no', 'yes', 'do', 'does', 'did',
    'your', 'our', 'ours', 'yours', 'what', 'which', 'when', 'how', 'why'
]);

const SENTENCE_SPLIT = /(?<=[.!?])\s+/;

function tokenize(text: string): string[] {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .split(/\s+/)
        .filter(w => w.length > 1 && !STOPWORDS.has(w));
}

/** Pick a key phrase from a sentence: prefer 2–4 word runs of significant tokens, else single best word. */
function extractKeyPhraseFromSentence(sentence: string, allTerms: Set<string>): string | null {
    const tokens = tokenize(sentence);
    if (tokens.length === 0) return null;
    const freq = new Map<string, number>();
    for (const t of tokens) freq.set(t, (freq.get(t) || 0) + 1);
    // Prefer multi-word phrase: longest run of tokens that are "content" (not only once in sentence)
    let best: string | null = null;
    let bestScore = 0;
    for (let len = Math.min(4, tokens.length); len >= 1; len--) {
        for (let i = 0; i <= tokens.length - len; i++) {
            const phrase = tokens.slice(i, i + len).join(' ');
            if (phrase.length < 3) continue;
            const score = len * 10 + (allTerms.has(phrase) ? 5 : 0);
            if (score > bestScore) {
                bestScore = score;
                best = phrase;
            }
        }
    }
    if (best) return best;
    const single = tokens.reduce((a, b) => (freq.get(a)! >= (freq.get(b) || 0) ? a : b));
    return single.length > 2 ? single : null;
}

/** Capitalize first letter for display. */
function capitalize(s: string): string {
    return s.charAt(0).toUpperCase() + s.slice(1);
}

export interface QuizQuestion {
    question: string;
    options: string[];
    correctAnswer: number;
}

export type DifficultyMode = 'easy' | 'challenging' | 'very_challenging';

/** Shuffle array in place and return the new index of the first element. */
function shuffleAndGetCorrectIndex<T>(arr: T[], correctItem: T): number {
    for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr.indexOf(correctItem);
}

/**
 * Generate MCQs from course content.
 * - Key sentences/terms extracted from content; questions are formed around key phrases.
 * - Distractors are other key terms from the same content (plausible but wrong).
 * - Difficulty: easy = fewer, remember-style; very_challenging = more, analyze-style.
 */
export function generateQuizFromContent(
    content: string,
    difficulty: DifficultyMode
): QuizQuestion[] {
    const cleaned = content.replace(/\s+/g, ' ').trim();
    if (!cleaned || cleaned.length < 50) return [];

    const sentences = cleaned.split(SENTENCE_SPLIT).map(s => s.trim()).filter(s => s.length > 20);
    if (sentences.length === 0) return [];

    const wordFreq = new Map<string, number>();
    for (const s of sentences) {
        for (const w of tokenize(s)) wordFreq.set(w, (wordFreq.get(w) || 0) + 1);
    }

    const scored = sentences.map((s, i) => {
        const words = tokenize(s);
        const score = words.reduce((sum, w) => sum + (wordFreq.get(w) || 0), 0);
        return { index: i, sentence: s, score };
    });

    const topSentences = scored
        .sort((a, b) => b.score - a.score)
        .slice(0, Math.min(10, scored.length))
        .sort((a, b) => a.index - b.index);

    const allTermsSet = new Set<string>();
    const keyPhrases: string[] = [];
    for (const { sentence } of topSentences) {
        const phrase = extractKeyPhraseFromSentence(sentence, allTermsSet);
        if (phrase) {
            keyPhrases.push(phrase);
            allTermsSet.add(phrase);
            tokenize(phrase).forEach(t => allTermsSet.add(t));
        }
    }

    const uniquePhrases = [...new Set(keyPhrases)].filter(p => p.length >= 2);
    if (uniquePhrases.length < 2) return [];

    const numQuestions = difficulty === 'easy' ? Math.min(3, uniquePhrases.length)
        : difficulty === 'challenging' ? Math.min(4, uniquePhrases.length)
            : Math.min(5, uniquePhrases.length);

    const questions: QuizQuestion[] = [];
    const usedCorrect = new Set<string>();

    for (let i = 0; i < numQuestions && i < topSentences.length; i++) {
        const { sentence } = topSentences[i];
        const correctPhrase = extractKeyPhraseFromSentence(sentence, allTermsSet);
        if (!correctPhrase || usedCorrect.has(correctPhrase)) continue;
        usedCorrect.add(correctPhrase);

        const distractors = uniquePhrases
            .filter(p => p !== correctPhrase)
            .slice(0, 4);
        if (distractors.length < 2) continue;

        const numOptions = Math.min(4, distractors.length + 1);
        const optionsSource = [correctPhrase, ...distractors.slice(0, numOptions - 1)];
        const displayOptions = optionsSource.map(p => capitalize(p));
        const correctIndex = shuffleAndGetCorrectIndex([...displayOptions], capitalize(correctPhrase));

        let questionText: string;
        if (difficulty === 'easy') {
            questionText = `What is "${correctPhrase}" in the context of this material?`;
        } else if (difficulty === 'challenging') {
            const truncated = sentence.length > 120 ? sentence.slice(0, 117) + '...' : sentence;
            questionText = `According to the material: "${truncated}" Which of the following best completes or summarizes this?`;
        } else {
            questionText = `Which option best describes or relates to this idea from the material: "${sentence.length > 80 ? sentence.slice(0, 77) + '...' : sentence}"?`;
        }

        questions.push({
            question: questionText,
            options: displayOptions,
            correctAnswer: correctIndex
        });
    }

    return questions;
}
