import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowLeft, Video, FileText, Brain, CheckCircle2 } from 'lucide-react';
import { Lesson } from '@/types/course';
import { InteractiveQuiz } from './InteractiveQuiz';

interface LessonViewProps {
  lesson: Lesson;
  onBack: () => void;
  onQuizComplete: (score: number) => void;
}

// Build YouTube embed URL from video (backend may send only id, not url)
function getVideoEmbedUrl(video: { id?: string; url?: string } | null): string {
  if (!video?.id && !video?.url) return '';
  if (video.url) return video.url.replace('watch?v=', 'embed/').split('&')[0];
  return `https://www.youtube.com/embed/${video.id}`;
}

export const LessonView = ({ lesson, onBack, onQuizComplete }: LessonViewProps) => {
  const [selectedVideo, setSelectedVideo] = useState(lesson.videos?.[0] || null);
  const isQuizOnlyLesson = lesson.title === 'Quiz';

  return (
    <div className="space-y-6 pb-8">
      <div className="flex items-center gap-4">
        <Button variant="outline" onClick={onBack} size="icon">
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl md:text-3xl font-bold">{lesson.title}</h1>
          {lesson.is_completed && (
            <div className="flex items-center gap-2 text-success mt-2">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-sm">Completed</span>
            </div>
          )}
        </div>
      </div>

      {isQuizOnlyLesson ? (
        <div className="space-y-4">
          {lesson.quiz_data ? (
            <InteractiveQuiz
              quiz={lesson.quiz_data}
              onComplete={onQuizComplete}
              previousScore={lesson.quiz_score}
            />
          ) : (
            <Card className="p-6 text-center bg-card/50 backdrop-blur-sm">
              <p className="text-muted-foreground">No quiz available.</p>
            </Card>
          )}
        </div>
      ) : (
      <Tabs defaultValue="videos" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3 bg-card/50">
          <TabsTrigger value="videos" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            <Video className="w-4 h-4 mr-2" />
            Videos
          </TabsTrigger>
          <TabsTrigger value="notes" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            <FileText className="w-4 h-4 mr-2" />
            Notes
          </TabsTrigger>
          <TabsTrigger value="quiz" className="data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
            <Brain className="w-4 h-4 mr-2" />
            Quiz
          </TabsTrigger>
        </TabsList>

        <TabsContent value="videos" className="space-y-4">
          <Card className="aspect-video bg-card/50 backdrop-blur-sm overflow-hidden flex items-center justify-center">
            {(() => {
              const embedUrl = getVideoEmbedUrl(selectedVideo);
              return embedUrl ? (
                <iframe
                  src={embedUrl}
                  title={selectedVideo?.title || 'Video'}
                  className="w-full h-full"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <div className="text-muted-foreground p-4 text-center">
                  <Video className="w-12 h-12 mx-auto mb-2 opacity-50" />
                  <p>No video available for this lesson.</p>
                </div>
              );
            })()}
          </Card>

          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {lesson.videos?.map((video) => (
              <Card
                key={video.id}
                className={`p-3 cursor-pointer transition-all hover:shadow-lg ${selectedVideo?.id === video.id ? 'ring-2 ring-primary shadow-lg shadow-primary/20' : ''
                  } bg-card/50 backdrop-blur-sm`}
                onClick={() => setSelectedVideo(video)}
              >
                <img
                  src={video.thumbnail}
                  alt={video.title}
                  className="w-full aspect-video object-cover rounded-md mb-2"
                />
                <p className="text-sm font-medium line-clamp-2">{video.title}</p>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="notes">
          <Card className="p-6 bg-card/50 backdrop-blur-sm">
            <div className="prose prose-invert max-w-none">
              <div className="text-base leading-relaxed whitespace-pre-wrap text-foreground">
                {lesson.notes || 'No notes available for this lesson yet.'}
              </div>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="quiz">
          {lesson.quiz_data ? (
            <InteractiveQuiz
              quiz={lesson.quiz_data}
              onComplete={onQuizComplete}
              previousScore={lesson.quiz_score}
            />
          ) : (
            <Card className="p-6 text-center bg-card/50 backdrop-blur-sm">
              <p className="text-muted-foreground">No quiz available for this lesson yet.</p>
            </Card>
          )}
        </TabsContent>
      </Tabs>
      )}
    </div>
  );
};
