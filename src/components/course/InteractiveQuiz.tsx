import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import { CheckCircle2, XCircle, Trophy } from 'lucide-react';
import { Quiz } from '@/types/course';

interface InteractiveQuizProps {
  quiz: Quiz;
  onComplete: (score: number) => void;
  previousScore?: number | null;
}

export const InteractiveQuiz = ({ quiz, onComplete, previousScore }: InteractiveQuizProps) => {
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [selectedAnswer, setSelectedAnswer] = useState<number | null>(null);
  const [answers, setAnswers] = useState<number[]>([]);
  const [showResult, setShowResult] = useState(false);
  const [score, setScore] = useState(0);

  const handleAnswerSelect = (answerIndex: number) => {
    setSelectedAnswer(answerIndex);
  };

  const handleNext = () => {
    if (selectedAnswer === null) return;

    const newAnswers = [...answers, selectedAnswer];
    setAnswers(newAnswers);

    if (currentQuestion < quiz.questions.length - 1) {
      setCurrentQuestion(currentQuestion + 1);
      setSelectedAnswer(null);
    } else {
      // Calculate score
      const finalScore = newAnswers.reduce((acc, answer, index) => {
        return answer === quiz.questions[index].correctAnswer ? acc + 1 : acc;
      }, 0);
      setScore(finalScore);
      setShowResult(true);
      onComplete(finalScore);
    }
  };

  const handleRetake = () => {
    setCurrentQuestion(0);
    setSelectedAnswer(null);
    setAnswers([]);
    setShowResult(false);
    setScore(0);
  };

  if (showResult) {
    const percentage = Math.round((score / quiz.questions.length) * 100);
    const passed = percentage >= 60;

    return (
      <Card className="p-8 text-center space-y-6 bg-card/50 backdrop-blur-sm">
        <div className="flex justify-center">
          {passed ? (
            <div className="p-4 rounded-full bg-success/20">
              <Trophy className="w-16 h-16 text-success" />
            </div>
          ) : (
            <div className="p-4 rounded-full bg-warning/20">
              <XCircle className="w-16 h-16 text-warning" />
            </div>
          )}
        </div>

        <div className="space-y-2">
          <h3 className="text-3xl font-bold">
            {passed ? 'Congratulations!' : 'Keep Practicing!'}
          </h3>
          <p className="text-xl text-muted-foreground">
            You scored {score} out of {quiz.questions.length}
          </p>
          <p className="text-4xl font-bold text-primary">{percentage}%</p>
        </div>

        {previousScore != null && previousScore !== score && (
          <p className="text-sm text-muted-foreground">
            Previous score: {previousScore}/{quiz.questions.length}
          </p>
        )}

        <div className="space-y-4 pt-4">
          <h4 className="font-semibold">Review Answers:</h4>
          {quiz.questions.map((q, index) => {
            const userAnswerIndex = answers[index];
            const correct = userAnswerIndex === q.correctAnswer;
            const userAnswerText = typeof userAnswerIndex === 'number' && q.options[userAnswerIndex] != null
              ? q.options[userAnswerIndex]
              : '—';
            return (
              <div key={index} className="text-left p-4 rounded-lg bg-background/50">
                <p className="font-medium mb-2">{q.question}</p>
                <div className="flex items-center gap-2 text-sm">
                  {correct ? (
                    <CheckCircle2 className="w-4 h-4 text-success" />
                  ) : (
                    <XCircle className="w-4 h-4 text-destructive" />
                  )}
                  <span className={correct ? 'text-success' : 'text-destructive'}>
                    Your answer: {userAnswerText}
                  </span>
                </div>
                {!correct && (
                  <p className="text-sm text-muted-foreground mt-1">
                    Correct answer: {q.options[q.correctAnswer]}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        <Button onClick={handleRetake} variant="outline" className="w-full">
          Retake Quiz
        </Button>
      </Card>
    );
  }

  const question = quiz.questions[currentQuestion];
  const radioGroupKey = `q-${currentQuestion}`;
  const optionId = (i: number) => `q${currentQuestion}-opt-${i}`;

  return (
    <Card className="p-6 space-y-6 bg-card/50 backdrop-blur-sm">
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Question {currentQuestion + 1} of {quiz.questions.length}
          </span>
          <span className="text-sm font-medium text-primary">
            {Math.round(((currentQuestion + 1) / quiz.questions.length) * 100)}%
          </span>
        </div>
        <h3 className="text-xl font-semibold">{question.question}</h3>
      </div>

      <RadioGroup
        key={radioGroupKey}
        value={selectedAnswer !== null ? selectedAnswer.toString() : ''}
        onValueChange={(val) => (val !== '' ? handleAnswerSelect(parseInt(val, 10)) : undefined)}
      >
        <div className="space-y-3">
          {question.options.map((option, index) => (
            <div key={optionId(index)} className="flex items-center space-x-3 p-4 rounded-lg border border-border hover:border-primary transition-colors cursor-pointer">
              <RadioGroupItem value={index.toString()} id={optionId(index)} />
              <Label htmlFor={optionId(index)} className="flex-1 cursor-pointer">
                {option}
              </Label>
            </div>
          ))}
        </div>
      </RadioGroup>

      <Button
        onClick={handleNext}
        disabled={selectedAnswer === null}
        className="w-full"
        size="lg"
      >
        {currentQuestion < quiz.questions.length - 1 ? 'Next Question' : 'Submit Quiz'}
      </Button>
    </Card>
  );
};
