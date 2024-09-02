# LLM Personal Assistant

This project is a personal assistant powered by Large Language Model (LLM) technology, designed to help individuals with ADHD manage their tasks and schedules more effectively.

## Features

- Task Management: Create, read, update, and delete tasks
- LLM Integration: Analyze tasks using Anthropic's Claude model
- Google Calendar Integration: View and manage your upcoming events
- User-friendly Interface: Built with React and Material-UI

## Prerequisites

- Python 3.8+
- Node.js 14+
- npm 6+

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

4. Set up your `.env` file with the necessary environment variables.

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

To start both the backend and frontend, use the provided script:

```
./start_app.sh
```

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.