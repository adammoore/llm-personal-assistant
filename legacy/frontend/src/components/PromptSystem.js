import React, { useState, useEffect } from 'react';
import {
  Typography,
  Button,
  TextField,
  Card,
  CardContent,
  CardActions,
  Box
} from '@mui/material';
import axios from 'axios';

const PromptSystem = () => {
  const [prompts, setPrompts] = useState([]);
  const [currentPrompt, setCurrentPrompt] = useState(null);
  const [response, setResponse] = useState('');

  useEffect(() => {
    fetchPrompts();
  }, []);

  const fetchPrompts = async () => {
    try {
      const result = await axios.get('http://localhost:8000/prompts/daily');
      setPrompts(result.data);
      if (result.data.length > 0) {
        setCurrentPrompt(result.data[0]);
      }
    } catch (error) {
      console.error('Error fetching prompts:', error);
    }
  };

  const handleSubmit = async () => {
    try {
      await axios.post('http://localhost:8000/prompts/respond', {
        prompt_id: currentPrompt.id,
        response: response
      });
      setResponse('');
      // Move to the next prompt or finish if all prompts are answered
      const currentIndex = prompts.findIndex(p => p.id === currentPrompt.id);
      if (currentIndex < prompts.length - 1) {
        setCurrentPrompt(prompts[currentIndex + 1]);
      } else {
        setCurrentPrompt(null);
      }
    } catch (error) {
      console.error('Error submitting response:', error);
    }
  };

  if (!currentPrompt) {
    return <Typography>No more prompts for now. Check back later!</Typography>;
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" component="div" gutterBottom>
          {currentPrompt.question}
        </Typography>
        <TextField
          fullWidth
          multiline
          rows={4}
          variant="outlined"
          value={response}
          onChange={(e) => setResponse(e.target.value)}
          margin="normal"
        />
      </CardContent>
      <CardActions>
        <Button onClick={handleSubmit} variant="contained" color="primary">
          Submit
        </Button>
      </CardActions>
    </Card>
  );
};

export default PromptSystem;