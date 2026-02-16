import { PlannerAgent } from './PlannerAgent';
import { ContentAgent } from './ContentAgent';
import { VerifierAgent } from './VerifierAgent';
import { searchVideos, getVideoMetadata } from '../services/youtubeService';
import { YoutubeTranscript } from 'youtube-transcript';
import fs from 'fs';
import path from 'path';
import os from 'os';
import ytdl from 'ytdl-core';
import { GoogleAIFileManager } from "@google/generative-ai/server";
import { DifficultyManager } from './DifficultyManager';
import { generateLocalContentFromTranscript } from '../utils/simpleSummarizer';
import { transcribeWithASR } from '../services/asrService';
import { generateQuizFromContent, type DifficultyMode } from '../utils/localQuizGenerator';

// Helper for audio download (refactored from controller)
const downloadAudio = async (url: string, videoId: string): Promise<string> => {
    return new Promise((resolve, reject) => {
        const tempFilePath = path.join(os.tmpdir(), `${videoId}.mp3`);
        const stream = ytdl(url, { quality: 'lowestaudio', filter: 'audioonly' });
        stream.pipe(fs.createWriteStream(tempFilePath))
            .on('finish', () => resolve(tempFilePath))
            .on('error', (err) => reject(err));
    });
};

const fileManager = new GoogleAIFileManager(process.env.GEMINI_API_KEY || '');

export class Orchestrator {
    private planner: PlannerAgent;
    private contentAgent: ContentAgent;
    private verifier: VerifierAgent;
    private sendEvent: (event: string, data: any) => void;

    constructor(sendEvent: (event: string, data: any) => void) {
        this.planner = new PlannerAgent();
        this.contentAgent = new ContentAgent();
        this.verifier = new VerifierAgent();
        this.sendEvent = sendEvent;
    }

    async planCourse(topic: string) {
        this.sendEvent('progress', { percent: 10, message: "📋 Planner Agent: Analyzing Instructional Design..." });
        const plan = await this.planner.planCurriculum(topic);
        this.sendEvent('progress', { percent: 20, message: `📋 Planner: Designed ${plan.type} course with ${plan.lessons.length} lessons.` });
        return plan;
    }

    async executeCourse(courseId: string, plan: any, userId: string, topic: string) {
        const difficultyManager = new DifficultyManager();
        const contentMode = process.env.CONTENT_MODE || 'local'; // 'local' = no Gemini in execution
        const results: any[] = [];
        let completedLessons = 0;
        const totalLessons = plan.lessons.length;
        const executeStartTime = Date.now();
        let ttftEmitted = false;

        // Step 2: Execution Loop
        for (const lessonPlan of plan.lessons) {
            // Adaptive Difficulty Check
            const difficultyMode = await difficultyManager.determineDifficulty(userId, courseId);

            this.sendEvent('progress', {
                percent: 20 + Math.floor((completedLessons / totalLessons) * 70),
                message: `🎥 [${difficultyMode}] Searching content for: "${lessonPlan.title}"...`
            });

            // A. Search Videos for this subtopic/title.
            // Requirement: "subtopic names will be combined with the educational
            // keywords and sent as a query to YouTube Data API v3 one by one".
            // The youtubeService takes care of appending educational keywords,
            // performing search.list (maxResults=30, order=relevance), then
            // videos.list(part=statistics) and returning the top 5 by likeCount.
            const videos = await searchVideos(lessonPlan.title);
            if (videos.length === 0) {
                console.warn(`No video found for ${lessonPlan.title}`);
                results.push(this.createEmptyLesson(lessonPlan));
                continue;
            }
            // Primary video used for any single‑video fallbacks is the
            // highest-ranked (most likes) among the shortlisted set.
            const primaryVideo = videos[0];
            const videoId = primaryVideo.id?.videoId;

            if (!videoId) {
                console.warn(`No valid video ID found for ${lessonPlan.title}`);
                results.push(this.createEmptyLesson(lessonPlan));
                continue;
            }

            const videoMetadata = await getVideoMetadata(videoId);

            // B. Get Content (Captions / Transcripts)
            // For every video: first try direct captions; if not possible, extract via ASR for that video.
            // Merge all transcripts (from captions + ASR per video) for content generation.
            let mergedTranscriptText = "";
            let generatedContent: any = {};
            let usedASR = false;

            const perVideoTranscripts: string[] = [];

            for (const v of videos) {
                const vid = v.id?.videoId;
                if (!vid) continue;
                let text = "";
                try {
                    const transcriptEntries = await YoutubeTranscript.fetchTranscript(vid);
                    text = (transcriptEntries || []).map((t: { text: string }) => t.text).join(' ').trim();
                } catch (e) {
                    // Direct captions failed for this video
                }
                if (!text) {
                    this.sendEvent('progress', { message: `🎧 ASR: Transcribing video ${vid}...` });
                    try {
                        const youtubeUrl = `https://www.youtube.com/watch?v=${vid}`;
                        text = await transcribeWithASR(youtubeUrl);
                        usedASR = true;
                    } catch (err: any) {
                        console.warn(`ASR failed for video ${vid}:`, err?.message || err);
                    }
                }
                if (text) perVideoTranscripts.push(text);
            }

            mergedTranscriptText = perVideoTranscripts.join(' ').trim();

            if (!mergedTranscriptText) {
                this.sendEvent('progress', { message: `🔄 Last-resort ASR for first video...` });
                try {
                    const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;
                    mergedTranscriptText = await transcribeWithASR(youtubeUrl);
                    usedASR = true;
                } catch (err: any) {
                    console.error(`[Orchestrator] No transcript for "${lessonPlan.title}". ASR error:`, err?.message || err);
                }
            }

            if (!mergedTranscriptText) {
                const videoTitles = (videos as any[]).slice(0, 5).map((v: any) => v.snippet?.title || 'Video').join('. ');
                mergedTranscriptText = `Lesson: ${lessonPlan.title}. Recommended videos: ${videoTitles}. (Transcript could not be obtained; please watch the videos for full content.)`;
                console.warn(`[Orchestrator] Using fallback content for "${lessonPlan.title}".`);
            }

            // C. Course Content Generation from merged transcripts
            if (contentMode === 'local') {
                // Local summarization ONLY. No Gemini / Groq usage here.
                this.sendEvent('progress', {
                    message: `🧠 Local Summarizer: Summarizing merged transcripts for "${lessonPlan.title}"...`
                });
                // Existing summarizer already performs extractive summarization by
                // selecting the most informative sentences. Here we simply feed it
                // the merged captions from all selected videos for this subtopic.
                generatedContent = generateLocalContentFromTranscript(mergedTranscriptText);
                // Local quiz generation (no Gemini): key terms + MCQs with in-document distractors
                const quizDifficulty: DifficultyMode =
                    difficultyMode === 'Remedial' ? 'easy'
                        : difficultyMode === 'Advanced' ? 'very_challenging'
                            : 'challenging';
                const quizQuestions = generateQuizFromContent(generatedContent.content, quizDifficulty);
                generatedContent.quiz_data = { questions: quizQuestions };
            } else {
                // LLM-based content generation:
                // - Treat the merged captions from all top videos as the source text.
                // - Use the ContentAgent + VerifierAgent pipeline to create an
                //   abstractive, teacher‑like lesson from these captions.
                if (!usedASR) {
                    this.sendEvent('progress', { message: `🧠 Content Agent (${difficultyMode}): Analyzing transcript...` });

                    // 1. Extract Salient Phrases (GRPO Step 1)
                    const { phrases } = await this.contentAgent.extractSalientPhrases([mergedTranscriptText]);

                    // 2. Generate Draft with Adaptive Difficulty
                    generatedContent = await this.contentAgent.generateLessonContent(
                        mergedTranscriptText,
                        phrases,
                        lessonPlan.cognitive_level,
                        difficultyMode
                    );

                    // 3. Verification Loop
                    let attempts = 0;
                    let isValid = false;

                    while (!isValid && attempts < 2) {
                        this.sendEvent('progress', { message: `🛡️ Verifier Agent: Validating attempt ${attempts + 1}...` });

                        const verification = await this.verifier.verifyContent(
                            mergedTranscriptText,
                            generatedContent.content,
                            generatedContent.quiz_data.questions
                        );

                        if (verification.valid) {
                            isValid = true;
                            console.log("✅ Verification Passed");
                        } else {
                            console.warn("❌ Verification Failed:", verification.feedback);
                            attempts++;
                            if (attempts === 2) {
                                console.warn("Max retries reached, using best effort.");
                                isValid = true;
                            }
                        }
                    }
                } else {
                    // Audio Fallback with Gemini (when no captions and ASR is used)
                    this.sendEvent('progress', { message: `🎧 Content Agent: Audio Fallback for "${lessonPlan.title}"...` });
                    try {
                        const audioPath = await downloadAudio(`https://www.youtube.com/watch?v=${videoId}`, videoId);
                        const uploadResponse = await fileManager.uploadFile(audioPath, { mimeType: "audio/mp3" });

                        generatedContent = await this.contentAgent.processAudio(uploadResponse.file.uri, topic);

                        if (fs.existsSync(audioPath)) fs.unlinkSync(audioPath);
                    } catch (err) {
                        console.error("Audio processing failed", err);
                        results.push(this.createEmptyLesson(lessonPlan));
                        completedLessons++;
                        continue;
                    }
                }
            }

            const lessonResult = {
                title: lessonPlan.title,
                content: generatedContent.content,
                // Expose the top 5 shortlisted videos (ranked by likeCount)
                // for this subtopic back to the frontend.
                videos: videos
                    .map((v: any) => ({
                        id: v.id?.videoId,
                        title: v.snippet?.title,
                        thumbnail: v.snippet?.thumbnails?.high?.url
                    }))
                    .filter((v: any) => !!v.id),
                notes: generatedContent.notes,
                quiz_data: generatedContent.quiz_data,
                // Add metadata for adaptive learning
                cognitive_level: lessonPlan.cognitive_level,
                pedagogical_metadata: {
                    objectives: lessonPlan.objectives,
                    difficulty_mode: difficultyMode,
                    challenge_question: generatedContent.challenge_question
                }
            };
            results.push(lessonResult);
            if (!ttftEmitted && lessonResult.content) {
                const ttftSec = (Date.now() - executeStartTime) / 1000;
                this.sendEvent('ttft', { ttft_sec: Math.round(ttftSec * 100) / 100, lesson_index: completedLessons });
                ttftEmitted = true;
            }
            completedLessons++;
        }

        // Overall course quiz: one extra "lesson" named "Quiz" (appears in lessons list)
        const overallContent = results
            .map((r: any) => r.content)
            .filter(Boolean)
            .join('\n\n');
        if (overallContent) {
            const overallDifficulty = await difficultyManager.determineDifficulty(userId, courseId);
            const overallQuizDifficulty: DifficultyMode =
                overallDifficulty === 'Remedial' ? 'easy'
                    : overallDifficulty === 'Advanced' ? 'very_challenging'
                        : 'challenging';
            const overallQuestions = generateQuizFromContent(overallContent, overallQuizDifficulty);
            results.push({
                title: 'Quiz',
                content: 'Test your knowledge of the entire course. This quiz covers key concepts from all lessons.',
                videos: [],
                notes: 'Complete the quiz to reinforce your learning.',
                quiz_data: { questions: overallQuestions },
                cognitive_level: 'apply',
                pedagogical_metadata: {
                    objectives: ['Review key concepts across all lessons'],
                    difficulty_mode: overallDifficulty,
                    challenge_question: null
                }
            });
        }

        return results;
    }

    private createEmptyLesson(plan: any) {
        return {
            title: plan.title,
            content: "Content could not be generated.",
            videos: [],
            notes: "N/A",
            quiz_data: { questions: [] },
            cognitive_level: plan.cognitive_level || 'understand',
            pedagogical_metadata: {}
        };
    }
}
