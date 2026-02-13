// Simple local transcript summarizer that does NOT call any LLM.
// It performs a basic extractive summarization:
// - splits transcript into sentences
// - scores sentences by word frequency (ignoring stopwords)
// - returns the top N sentences in original order as the "content"
//
// Quiz generation is left empty on purpose to avoid additional complexity.

const STOPWORDS = new Set([
    'the', 'and', 'a', 'an', 'to', 'of', 'in', 'on', 'for', 'with', 'at', 'by',
    'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'this', 'that', 'these', 'those',
    'i', 'you', 'he', 'she', 'it', 'we', 'they', 'them', 'his', 'her', 'their',
    'as', 'from', 'or', 'but', 'if', 'then', 'so', 'because',
    'can', 'could', 'should', 'would', 'may', 'might',
    'not', 'no', 'yes', 'do', 'does', 'did',
    'your', 'our', 'ours', 'yours'
]);

const SENTENCE_SPLIT_REGEX = /(?<=[\.!?])\s+/;

function tokenize(text: string): string[] {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\s]/g, ' ')
        .split(/\s+/)
        .filter(w => w.length > 2 && !STOPWORDS.has(w));
}

export interface LocalGeneratedContent {
    content: string;
    notes: string;
    quiz_data: { questions: any[] };
    challenge_question: { question: string; key_concept: string };
}

export function generateLocalContentFromTranscript(
    transcript: string,
    maxSummarySentences: number = 8
): LocalGeneratedContent {
    const cleaned = transcript.replace(/\s+/g, ' ').trim();
    if (!cleaned) {
        return {
            content: 'No transcript content was available for this lesson.',
            notes: '- No content available.',
            quiz_data: { questions: [] },
            challenge_question: {
                question: 'Reflect on what you already know about this topic and write a short summary.',
                key_concept: 'prior_knowledge'
            }
        };
    }

    const sentences = cleaned.split(SENTENCE_SPLIT_REGEX).filter(s => s.trim().length > 0);

    // Build word frequency map over the whole transcript
    const freq = new Map<string, number>();
    for (const sentence of sentences) {
        for (const word of tokenize(sentence)) {
            freq.set(word, (freq.get(word) || 0) + 1);
        }
    }

    // Score each sentence by sum of word frequencies
    const scored = sentences.map((sentence, index) => {
        const words = tokenize(sentence);
        const score = words.reduce((sum, w) => sum + (freq.get(w) || 0), 0);
        return { index, sentence: sentence.trim(), score };
    });

    // Take top N by score, then sort by original order
    const top = scored
        .sort((a, b) => b.score - a.score)
        .slice(0, Math.min(maxSummarySentences, scored.length))
        .sort((a, b) => a.index - b.index);

    const summarySentences = top.map(s => s.sentence);
    const content = summarySentences.join(' ');

    const notes = summarySentences.map(s => `- ${s}`).join('\n');

    // Very simple challenge question from the highest‑scoring sentence
    const topSentence = scored.sort((a, b) => b.score - a.score)[0];
    const challengeQuestion = topSentence
        ? {
            question: `Explain this key idea in your own words: "${topSentence.sentence}"`,
            key_concept: topSentence.sentence.slice(0, 120)
        }
        : {
            question: 'Summarize the main idea of this lesson in your own words.',
            key_concept: 'main_idea'
        };

    return {
        content,
        notes,
        quiz_data: { questions: [] }, // no MCQs in local mode
        challenge_question: challengeQuestion
    };
}

