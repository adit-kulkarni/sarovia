# OpenAI Realtime API Demo - Python/React Language Learning Platform

This is a language learning platform that uses OpenAI's Realtime API for voice conversations, with automatic feedback generation and progress tracking.

## Features

### Core Features
- **Real-time Voice Conversations**: Practice speaking with AI tutors using OpenAI's Realtime API
- **Automatic Feedback**: AI analyzes your messages and provides detailed feedback on grammar, vocabulary, pronunciation, and more
- **Multi-language Support**: Practice English, Spanish, French, German, Italian, Portuguese, and Kannada
- **CEFR Level Adaptation**: Conversations adapt to your proficiency level (A1-C2)
- **Progress Analytics**: Track your learning progress with detailed charts and metrics

### Curriculum System
- **Structured Lessons**: Follow pre-designed lesson templates for systematic learning
- **Context-based Practice**: Practice in different scenarios (restaurant, market, introduction, etc.)
- **Lesson Templates**: Pre-built lessons with specific objectives and cultural elements

### 🆕 Custom Lesson Generation
**AI-Powered Weakness Targeting**: The platform now automatically identifies your recurring mistakes and generates personalized lessons to target your specific areas of weakness.

#### How it works:
1. **Weakness Analysis**: The system analyzes all your conversation feedback to identify patterns of mistakes
2. **Pattern Recognition**: Groups mistakes by category (grammar, vocabulary, etc.) and type (verb tense, ser vs estar, etc.)
3. **Smart Prioritization**: Focuses on the most frequent and severe mistake patterns
4. **Custom Lesson Creation**: Uses AI to generate targeted lessons with:
   - Specific objectives addressing your weaknesses
   - Tailored content and explanations
   - Practice activities focused on problem areas
   - Cultural context relevant to the lessons

#### Example Use Cases:
- **Spanish learners**: If you frequently confuse "ser" vs "estar", the system generates a custom lesson specifically about these verbs
- **German learners**: If you struggle with der/die/das articles, you get a lesson focused on German article usage
- **General grammar**: If you make consistent verb conjugation errors, you get targeted practice for that specific tense

#### Usage:
1. Practice normal conversations and receive feedback
2. After accumulating enough conversation data, go to the "Your Progress" section
3. View your "Weakness Analysis" to see recurring mistake patterns
4. Click "Generate Custom Lesson" to create a personalized lesson
5. Start practicing with your custom lesson designed for your specific needs

### Technical Features
- **WebSocket Communication**: Real-time audio streaming
- **Supabase Backend**: User authentication, data storage, and real-time features
- **JWT Authentication**: Secure user sessions
- **React/Next.js Frontend**: Modern, responsive user interface

## API Endpoints

### Custom Lesson Endpoints
- `GET /api/analyze_weaknesses?curriculum_id={id}` - Analyze user's mistake patterns
- `POST /api/generate_custom_lesson` - Generate a custom lesson based on weaknesses
- `GET /api/custom_lessons?curriculum_id={id}` - List custom lessons
- `POST /api/start_custom_lesson_conversation` - Start a conversation with a custom lesson
- `DELETE /api/custom_lessons/{id}` - Delete a custom lesson

### Other Endpoints
- `WebSocket /ws` - Real-time conversation handling
- `POST /api/hint` - Get conversation hints
- `POST /api/feedback` - Get feedback for messages
- `GET /api/conversations` - List user conversations
- `GET /api/curriculums` - Manage learning curriculums

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   cd frontend && npm install
   ```

2. **Environment Variables**:
   Create a `.env` file with:
   ```
   OPENAI_API_KEY=your_openai_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_KEY=your_supabase_service_key
   SUPABASE_JWT_SECRET=your_jwt_secret
   ```

3. **Database Setup**:
   Run the SQL schema files in your Supabase project:
   - `schema.sql`
   - `schema_feedback.sql`
   - `schema_custom_lessons.sql`

4. **Run the Application**:
   ```bash
   # Start backend
   python server.py
   
   # Start frontend (in another terminal)
   cd frontend && npm run dev
   ```

## Architecture

- **Backend**: FastAPI with WebSocket support
- **Frontend**: Next.js with React
- **Database**: Supabase (PostgreSQL)
- **Real-time**: WebSocket for audio streaming
- **AI**: OpenAI GPT-4 for lesson generation and feedback analysis

## Database Schema

### Core Tables
- `users` - User authentication and profiles
- `curriculums` - Language learning paths
- `conversations` - Voice conversation sessions
- `messages` - Individual messages in conversations
- `message_feedback` - AI-generated feedback for user messages

### Custom Lesson Tables
- `custom_lesson_templates` - AI-generated personalized lessons
- `lesson_templates` - Pre-built lesson templates

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.