import React from 'react';
import { Container, Typography } from '@material-ui/core';
import TaskList from './components/TaskList';
import TaskForm from './components/TaskForm';

function App() {
  return (
    <Container maxWidth="md">
      <Typography variant="h2" component="h1" gutterBottom>
        LLM Personal Assistant
      </Typography>
      <TaskForm onTaskAdded={() => {}} />
      <TaskList />
    </Container>
  );
}

export default App;