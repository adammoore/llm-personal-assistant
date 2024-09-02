# LLM Personal Assistant

An AI-powered personal assistant designed to help individuals with ADHD manage their tasks and schedules more effectively.

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

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Authors

- **Adam Vials Moore** - *Initial work* - [adammoore](https://github.com/adammoore)

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Anthropic for providing the Claude AI model
- Google Calendar API for schedule integration

## Contact

Adam Vials Moore - moore.adam@gmail.com

Project Link: [https://github.com/adammoore/llm-personal-assistant](https://github.com/adammoore/llm-personal-assistant)