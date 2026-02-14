from ..config.db import Database

class DifficultyManager:
    async def determine_difficulty(self, user_id: str, course_id: str) -> str:
        try:
            # 1. Get State: Last 3 lesson scores
            query = """
                SELECT quiz_score FROM lessons 
                WHERE course_id = $1 AND is_completed = true 
                ORDER BY order_index DESC LIMIT 3
            """
            rows = await Database.fetch(query, course_id)
            scores = [row['quiz_score'] or 0 for row in rows]

            if not scores:
                return 'Standard'

            avg_score = sum(scores) / len(scores)
            difficulty = 'Standard'
            reason = "Maintained Standard difficulty"

            # 2. Action Logic
            if avg_score < 50:
                difficulty = 'Remedial'
                reason = f"Average score {avg_score:.1f}% < 50%. Switching to Remedial."
            elif avg_score > 85:
                difficulty = 'Advanced'
                reason = f"Average score {avg_score:.1f}% > 85%. Switching to Advanced."

            # 3. Log Reward/Action
            await self.log_action(user_id, course_id, difficulty, reason)

            return difficulty

        except Exception as e:
            print(f"Error determining difficulty: {e}")
            return 'Standard'

    async def log_action(self, user_id: str, course_id: str, new_difficulty: str, reason: str):
        try:
            query = """
                INSERT INTO adaptive_actions (user_id, course_id, new_difficulty, reason) 
                VALUES ($1, $2, $3, $4)
            """
            await Database.execute(query, user_id, course_id, new_difficulty, reason)
        except Exception as e:
            print(f"Failed to log adaptive action: {e}")
