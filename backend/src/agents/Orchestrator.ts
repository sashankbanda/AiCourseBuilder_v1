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
            // We attempt to follow the described pipeline:
            // - For each of the top 5 videos for this subtopic, try to fetch
            //   captions via YouTubeTranscript (manual subtitles or auto‑generated).
            // - If none of the videos have captions, fall back to ASR (Whisper‑style)
            //   on the primary video.
            // - All available transcripts are merged and summarized together.
            let mergedTranscriptText = "";
            let generatedContent: any = {};
            let usedASR = false;

            const perVideoTranscripts: string[] = [];

            // Try to fetch captions for each shortlisted video (manual or auto).
            for (const v of videos) {
                const vid = v.id?.videoId;
                if (!vid) continue;
                try {
                    const transcriptEntries = await YoutubeTranscript.fetchTranscript(vid);
                    const text = transcriptEntries.map(t => t.text).join(' ').trim();
                    if (text) {
                        perVideoTranscripts.push(text);
                    }
                } catch (e) {
                    console.warn(`No captions available for video ${vid}, will rely on other videos or ASR fallback if needed.`);
                }
            }

            if (perVideoTranscripts.length > 0) {
                mergedTranscriptText = perVideoTranscripts.join(' ');
            }

            // If none of the top videos had captions, fall back to ASR on the primary one.
            if (!mergedTranscriptText) {
                this.sendEvent('progress', { message: `🎧 Local ASR: No captions found, transcribing audio for "${lessonPlan.title}"...` });
                try {
                    const youtubeUrl = `https://www.youtube.com/watch?v=${videoId}`;
                    mergedTranscriptText = await transcribeWithASR(youtubeUrl);
                    usedASR = true;
                } catch (err) {
                    console.error('ASR fallback failed', err);
                    results.push(this.createEmptyLesson(lessonPlan));
                    completedLessons++;
                    continue;
                }
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

            results.push({
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
