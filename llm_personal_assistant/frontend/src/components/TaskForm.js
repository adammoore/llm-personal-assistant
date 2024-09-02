import React, { useState } from 'react';
import { TextField, Button, Box, Tooltip } from '@mui/material';
import axios from 'axios';

const TaskForm = ({ onTaskAdded }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await axios.post('http://localhost:8000/tasks/', { title, description });
      setTitle('');
      setDescription('');
      onTaskAdded();
    } catch (error) {
      console.error('Error adding task:', error);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Tooltip title="Enter the title of your task">
          <TextField
            label="Title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            fullWidth
            required
          />
        </Tooltip>
        <Tooltip title="Provide a detailed description of your task">
          <TextField
            label="Description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={4}
          />
        </Tooltip>
        <Tooltip title="Click to add the task">
          <Button type="submit" variant="contained" color="primary">
            Add Task
          </Button>
        </Tooltip>
      </Box>
    </form>
  );
};

export default TaskForm;