import React, { useState, useEffect } from 'react';
import { TextField, Button, Box, Typography, Card, CardContent } from '@mui/material';
import axios from 'axios';

const actionLearningQuestions = [
  "How do you feel about this situation?",
  "What would be an ideal outcome or solution?",
  "What would be a good short-term goal?",
  "On a scale of 0-10 how achievable are my goals short-term or long-term?",
  "If low, what can I do to make them achievable?",
  "What are the effects of this situation on you?",
  "What are the effects of this situation on others?",
  "What are the effects of not doing anything?",
  "What have you tried so far?",
  "What have you not tried out fully?",
  "What other options are there?",
  "What is holding you back?",
  "What is really going on?",
  "What do you really want?",
  "Imagine someone whose advice you respect were here – what advice would they give?",
  "If you could change only one thing, what would it be?",
  "What help is available?",
  "What are you willing to commit to?",
  "What level of commitment do I have to this action on a scale of 1-10? What will I do to get the level of commitment higher?"
];

const DailyPrompt = () => {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [currentQuestion, setCurrentQuestion] = useState('');

  useEffect(() => {
    fetchDailyPrompt();
  }, []);

  const fetchDailyPrompt = async () => {
    try {
      const result = await axios.get('http://localhost:8000/prompts/daily');
      setPrompt(result.data[0].question);
    } catch (error) {
      console.error('Error fetching daily prompt:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post('http://localhost:8000/prompts/respond', {
        prompt_id: 1,
        response: response
      });
      setResponse('');
      setCurrentQuestion(actionLearningQuestions[Math.floor(Math.random() * actionLearningQuestions.length)]);
    } catch (error) {
      console.error('Error submitting response:', error);
    }
  };

  return (
    <Box sx={{ '& > :not(style)': { m: 1 } }}>
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Daily Prompt</Typography>
          <Typography variant="body1" gutterBottom>{prompt}</Typography>
          <TextField
            fullWidth
            label="Your Response"
            variant="outlined"
            multiline
            rows={4}
            value={response}
            onChange={(e) => setResponse(e.target.value)}
            sx={{ mt: 2 }}
          />
          <Button type="submit" variant="contained" color="primary" onClick={handleSubmit} sx={{ mt: 2 }}>
            Submit
          </Button>
        </CardContent>
      </Card>
      {currentQuestion && (
        <Card sx={{ mt: 2 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>Reflection Question</Typography>
            <Typography variant="body1">{currentQuestion}</Typography>
          </CardContent>
        </Card>
      )}
    </Box>
  );
};

export default DailyPrompt;