import React, { useState, useEffect } from 'react';
import { Accordion, AccordionSummary, AccordionDetails, Typography, TextField, Button, Checkbox, Chip, IconButton } from '@mui/material';
import { Edit, Delete, Save, Cancel, ExpandMore } from '@mui/icons-material';
import axios from 'axios';

const TaskList = () => {
  const [tasks, setTasks] = useState([]);
  const [editingTask, setEditingTask] = useState(null);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const response = await axios.get('http://localhost:8000/tasks/');
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };


  const handleToggleComplete = async (id) => {
    try {
      const task = tasks.find(t => t.id === id);
      await axios.put(`http://localhost:8000/tasks/${id}`, {
        ...task,
        completed: !task.completed
      });
      fetchTasks();
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`http://localhost:8000/tasks/${id}`);
      fetchTasks();
    } catch (error) {
      console.error('Error deleting task:', error);
    }
  };

  const handleEdit = (task) => {
    setEditingTask({ ...task });
  };

  const handleSave = async () => {
    try {
      await axios.put(`http://localhost:8000/tasks/${editingTask.id}`, editingTask);
      setEditingTask(null);
      fetchTasks();
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const handleCancelEdit = () => {
    setEditingTask(null);
  };


  return (
    <div>
      {tasks.map((task) => (
        <Accordion key={task.id}>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography sx={{ width: '33%', flexShrink: 0 }}>{task.title}</Typography>
            <Typography sx={{ color: 'text.secondary' }}>
              {task.completed ? 'Completed' : 'Pending'}
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {editingTask && editingTask.id === task.id ? (
              <>
                <TextField
                  fullWidth
                  label="Title"
                  value={editingTask.title}
                  onChange={(e) => setEditingTask({ ...editingTask, title: e.target.value })}
                  margin="normal"
                />
                <TextField
                  fullWidth
                  label="Description"
                  value={editingTask.description}
                  onChange={(e) => setEditingTask({ ...editingTask, description: e.target.value })}
                  margin="normal"
                  multiline
                  rows={2}
                />
                <Button startIcon={<Save />} onClick={handleSave} sx={{ mr: 1 }}>
                  Save
                </Button>
                <Button startIcon={<Cancel />} onClick={handleCancelEdit}>
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <Typography>{task.description}</Typography>
                <Chip label={task.category || 'Uncategorized'} size="small" sx={{ mt: 1, mr: 1 }} />
                <Checkbox
                  checked={task.completed}
                  onChange={() => handleToggleComplete(task.id)}
                  inputProps={{ 'aria-label': 'Task completion status' }}
                />
                <IconButton aria-label="edit" onClick={() => handleEdit(task)} sx={{ mr: 1 }}>
                  <Edit />
                </IconButton>
                <IconButton aria-label="delete" onClick={() => handleDelete(task.id)}>
                  <Delete />
                </IconButton>
              </>
            )}
          </AccordionDetails>
        </Accordion>
      ))}
    </div>
  );
};

export default TaskList;