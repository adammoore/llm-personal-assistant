# LLM Personal Assistant

An AI-powered personal assistant designed to help individuals, especially those with ADHD, manage their tasks and schedules more effectively.

## Features

- Task Management: Create, read, update, and delete tasks with ease
- LLM Integration: Analyze tasks using Anthropic's Claude model for intelligent suggestions
- Google Calendar Integration: View and manage your upcoming events seamlessly
- User-friendly Interface: Built with React and Material-UI, optimized for neurodiverse users
- AI Autonomy Controls: Customize the level of AI assistance to suit your needs

## Prerequisites

- Python 3.8+
- Node.js 14+
- npm 6+
- Google Cloud Console account with Calendar API enabled
- Anthropic API key

## Setup

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use `.venv\Scripts\activate`
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your `.env` file with the necessary environment variables:
   ```
   DATABASE_URL=sqlite:///./test.db
   ANTHROPIC_API_KEY=your_anthropic_api_key
   SECRET_KEY=your_secret_key
   GOOGLE_CLIENT_ID=your_google_client_id
   GOOGLE_CLIENT_SECRET=your_google_client_secret
   ```

5. Place your `client_secret.json` file (obtained from Google Cloud Console) in the backend directory.

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

## Running the Application

1. Start the backend:
   ```
   cd backend
   uvicorn main:app --reload
   ```

2. Start the frontend:
   ```
   cd frontend
   npm start
   ```

3. Open your browser and navigate to `http://localhost:3000`

## Accessibility Features

- High contrast mode for better readability
- Customizable font sizes
- Keyboard shortcuts for common actions
- Screen reader-friendly components
- Clear and concise error messages

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Authors

- **Adam Vials Moore** - *Initial work* - [adammoore](https://github.com/adammoore)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Anthropic for providing the Claude AI model
- Google Calendar API for schedule integration
- The ADHD and neurodiversity communities for inspiration and feedback