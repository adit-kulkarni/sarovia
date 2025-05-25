export interface Mistake {
  category: string;
  type: string;
  error: string;
  correction: string;
  explanation: string;
  severity: 'minor' | 'moderate' | 'critical';
  languageFeatureTags?: string[];
}

export interface Feedback {
  messageId: string;
  originalMessage: string;
  mistakes: Mistake[];
  hasMistakes: boolean;
  timestamp: string;
}

export interface FeedbackCardProps {
  feedback: Feedback;
  onFeedbackClick: (messageId: string) => void;
}

export interface FeedbackPanelProps {
  feedbacks: Feedback[];
  onFeedbackClick: (messageId: string) => void;
}

export interface ChatBubbleProps {
  message: Message;
  hasFeedback: boolean;
  onFeedbackClick: () => void;
}

export const mistakeCategoryEmojis: Record<string, string> = {
  grammar: '📚',
  vocabulary: '🗣️',
  spelling: '✏️',
  punctuation: '🔤',
  syntax: '🧩',
  'word choice': '🎯',
  'register/formality': '🕴️',
  other: '❓',
};

// Message type for chat UI
export interface Message {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
  feedback?: Feedback; // Optional feedback info
} 