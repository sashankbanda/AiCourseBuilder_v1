import pool from '../config/db';

export type DifficultyLevel = 'Remedial' | 'Standard' | 'Advanced';

export class DifficultyManager {

    // Determine difficulty based on user's recent performance (State)
    async determineDifficulty(userId: string, courseId: string): Promise<DifficultyLevel> {
        // 1. Get State: Last 3 lesson scores
        // We assume 'lessons' table is updated with scores as users complete them.
        // Since we are generating the *next* lesson, we look at history.

        // Note: In the current generation flow, if we pre-generate all lessons at once, we can't adapt *between* lessons 
        // unless the generation is JIT (Just-In-Time) or we update the 'draft' lessons later.
        // The user request says "The Orchestrator then resumes the loop".
        // If we generate all at once, we assume this logic applies if we were re-generating or if specific previous context exists.
        // However, for a *new* course, history might be empty, so we default to Standard.

        try {
            const { rows } = await pool.query(
                `SELECT quiz_score FROM learning_states 
                 WHERE user_id = $1 AND course_id = $2
                 ORDER BY created_at DESC LIMIT 1`, // Simplified to use learning_states aggregate or we need a specific 'actions' log
                [userId, courseId]
            );

            // Better Approach: Query the 'lessons' table (if we had completed lessons history for this user/topic?)
            // Or 'adaptive_actions' to see past performance. 
            // The prompt says "Retrieve the last 3 quiz scores from learning_states". 
            // My schema for `learning_states` has `average_quiz_score`. 
            // I'll query the actual `lessons` table for *completed* lessons in this course to get specific recent scores.

            const historyQuery = await pool.query(
                `SELECT quiz_score FROM lessons 
                 WHERE course_id = $1 AND is_completed = true 
                 ORDER BY order_index DESC LIMIT 3`,
                [courseId]
            );

            const scores = historyQuery.rows.map((r: { quiz_score: number | null }) => r.quiz_score || 0);

            if (scores.length === 0) return 'Standard';

            const avgScore = scores.reduce((a: number, b: number) => a + b, 0) / scores.length;
            let difficulty: DifficultyLevel = 'Standard';
            let reason = "Maintained Standard difficulty";

            // 2. Action Logic
            if (avgScore < 50) {
                difficulty = 'Remedial';
                reason = `Average score ${avgScore.toFixed(1)}% < 50%. Switching to Remedial.`;
            } else if (avgScore > 85) {
                difficulty = 'Advanced';
                reason = `Average score ${avgScore.toFixed(1)}% > 85%. Switching to Advanced.`;
            }

            // 3. Log Reward/Action
            await this.logAction(userId, courseId, difficulty, reason);

            return difficulty;

        } catch (error) {
            console.error("Error determining difficulty:", error);
            return 'Standard';
        }
    }

    private async logAction(userId: string, courseId: string, newDifficulty: string, reason: string) {
        try {
            await pool.query(
                `INSERT INTO adaptive_actions (user_id, course_id, new_difficulty, reason) VALUES ($1, $2, $3, $4)`,
                [userId, courseId, newDifficulty, reason]
            );
        } catch (e) {
            console.error("Failed to log adaptive action", e);
        }
    }
}
