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
        const results = [];
        let completedLessons = 0;
        const totalLessons = plan.lessons.length;

        // Step 2: Execution Loop
        for (const lessonPlan of plan.lessons) {
            // Adaptive Difficulty Check
            const difficultyMode = await difficultyManager.determineDifficulty(userId, courseId);

            this.sendEvent('progress', {
                percent: 20 + Math.floor((completedLessons / totalLessons) * 70),
                message: `🎥 [${difficultyMode}] Searching content for: "${lessonPlan.title}"...`
            });

            // A. Search Video
            const videos = await searchVideos(lessonPlan.search_queries[0]);
            if (videos.length === 0) {
                console.warn(`No video found for ${lessonPlan.title}`);
                results.push(this.createEmptyLesson(lessonPlan));
                continue;
            }
            const video = videos[0];
            const videoId = video.id?.videoId;

            if (!videoId) {
                console.warn(`No valid video ID found for ${lessonPlan.title}`);
                results.push(this.createEmptyLesson(lessonPlan));
                continue;
            }

            const videoMetadata = await getVideoMetadata(videoId);

            // B. Get Content (Transcript or Audio)
            let transcriptText = "";
            let generatedContent: any = {};
            let isAudioFallback = false;

            try {
                const transcript = await YoutubeTranscript.fetchTranscript(videoId);
                transcriptText = transcript.map(t => t.text).join(' ');
            } catch (e) {
                isAudioFallback = true;
            }

            // C. Generate Content
            if (contentMode === 'local') {
                // Local summarization ONLY. No Gemini / Groq usage here.
                if (isAudioFallback) {
                    this.sendEvent('progress', { message: `🎧 Local ASR: Transcribing audio for "${lessonPlan.title}"...` });
                    try {
                        const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;
                        transcriptText = await transcribeWithASR(youtubeUrl);
                        this.sendEvent('progress', { message: `🧠 Local Summarizer: Summarizing ASR transcript for "${lessonPlan.title}"...` });
                        generatedContent = generateLocalContentFromTranscript(transcriptText);
                    } catch (err) {
                        console.error('ASR fallback failed', err);
                        results.push(this.createEmptyLesson(lessonPlan));
                        completedLessons++;
                        continue;
                    }
                } else {
                    this.sendEvent('progress', { message: `🧠 Local Summarizer: Summarizing transcript for "${lessonPlan.title}"...` });
                    generatedContent = generateLocalContentFromTranscript(transcriptText);
                }

            } else {
                // LLM-based content generation (original behavior)
                if (!isAudioFallback) {
                    this.sendEvent('progress', { message: `🧠 Content Agent (${difficultyMode}): Analyzing transcript...` });

                    // 1. Extract Salient Phrases (GRPO Step 1)
                    const { phrases } = await this.contentAgent.extractSalientPhrases([transcriptText]);

                    // 2. Generate Draft with Adaptive Difficulty
                    generatedContent = await this.contentAgent.generateLessonContent(transcriptText, phrases, lessonPlan.cognitive_level, difficultyMode);

                    // 3. Verification Loop
                    let attempts = 0;
                    let isValid = false;

                    while (!isValid && attempts < 2) {
                        this.sendEvent('progress', { message: `🛡️ Verifier Agent: Validating attempt ${attempts + 1}...` });

                        const verification = await this.verifier.verifyContent(transcriptText, generatedContent.content, generatedContent.quiz_data.questions);

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
                    // Audio Fallback with Gemini
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

            results.push({
                title: lessonPlan.title,
                content: generatedContent.content,
                videos: [{
                    id: videoId,
                    title: video.snippet?.title,
                    thumbnail: video.snippet?.thumbnails?.high?.url
                }],
                notes: generatedContent.notes,
                quiz_data: generatedContent.quiz_data,
                // Add metadata for adaptive learning
                cognitive_level: lessonPlan.cognitive_level,
                pedagogical_metadata: {
                    objectives: lessonPlan.objectives,
                    difficulty_mode: difficultyMode,
                    challenge_question: generatedContent.challenge_question
                }
            });

            completedLessons++;
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
