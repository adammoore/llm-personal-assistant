import React, { useState, useEffect } from 'react';
import {
  Accordion, AccordionSummary, AccordionDetails, Typography, Checkbox,
  IconButton, Tooltip, TextField, Select, MenuItem, FormControlLabel,
  Switch, Box, Chip
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import SaveIcon from '@mui/icons-material/Save';
import CancelIcon from '@mui/icons-material/Cancel';
import axios from 'axios';

const TaskList = () => {
  const [tasks, setTasks] = useState([]);
  const [editingTask, setEditingTask] = useState(null);
  const [hideCompleted, setHideCompleted] = useState(false);
  const [useTickTick, setUseTickTick] = useState(false);

  useEffect(() => {
    fetchTasks();
  }, [useTickTick]);

  const fetchTasks = async () => {
    try {
      const response = await axios.get(`http://localhost:8000/tasks${useTickTick ? '?source=ticktick' : ''}`);
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const handleToggleComplete = async (task) => {
    try {
      const updatedTask = { ...task, completed: !task.completed };
      await axios.put(`http://localhost:8000/tasks/${task.id}${useTickTick ? '?source=ticktick' : ''}`, updatedTask);
      fetchTasks();
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const handleEdit = (task) => {
    setEditingTask({ ...task });
  };

  const handleSave = async () => {
    try {
      await axios.put(`http://localhost:8000/tasks/${editingTask.id}${useTickTick ? '?source=ticktick' : ''}`, editingTask);
      setEditingTask(null);
      fetchTasks();
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const handleDelete = async (id) => {
    try {
      await axios.delete(`http://localhost:8000/tasks/${id}${useTickTick ? '?source=ticktick' : ''}`);
      fetchTasks();
    } catch (error) {
      console.error('Error deleting task:', error);
    }
  };

  const filteredTasks = hideCompleted ? tasks.filter(task => !task.completed) : tasks;

  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        <FormControlLabel
          control={<Switch checked={hideCompleted} onChange={() => setHideCompleted(!hideCompleted)} />}
          label="Hide Completed Tasks"
        />
        <FormControlLabel
          control={<Switch checked={useTickTick} onChange={() => setUseTickTick(!useTickTick)} />}
          label="Use TickTick"
        />
      </Box>
      {filteredTasks.map((task) => (
        <Accordion
          key={task.id}
          sx={{
            bgcolor: task.completed ? 'action.disabledBackground' : 'background.paper',
            '&:hover': { bgcolor: 'action.hover' },
          }}
        >
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            aria-label="Expand"
            aria-controls="additional-actions1-content"
            id="additional-actions1-header"
          >
            <Checkbox
              checked={task.completed}
              onChange={() => handleToggleComplete(task)}
              onClick={(event) => event.stopPropagation()}
              onFocus={(event) => event.stopPropagation()}
            />
            <Typography sx={{ width: '33%', flexShrink: 0 }}>{task.title}</Typography>
            <Chip label={task.category || 'Uncategorized'} size="small" />
          </AccordionSummary>
          <AccordionDetails>
            {editingTask && editingTask.id === task.id ? (
              <Box>
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
                <TextField
                  fullWidth
                  label="Category"
                  value={editingTask.category}
                  onChange={(e) => setEditingTask({ ...editingTask, category: e.target.value })}
                  margin="normal"
                />
                <Box sx={{ mt: 2 }}>
                  <Tooltip title="Save changes">
                    <IconButton onClick={handleSave}>
                      <SaveIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Cancel editing">
                    <IconButton onClick={() => setEditingTask(null)}>
                      <CancelIcon />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            ) : (
              <Box>
                <Typography>{task.description}</Typography>
                <Box sx={{ mt: 2 }}>
                  <Tooltip title="Edit task">
                    <IconButton onClick={() => handleEdit(task)}>
                      <EditIcon />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete task">
                    <IconButton onClick={() => handleDelete(task.id)}>
                      <DeleteIcon />
                    </IconButton>
                  </Tooltip>
                </Box>
              </Box>
            )}
          </AccordionDetails>
        </Accordion>
      ))}
    </Box>
  );
};

export default TaskList;