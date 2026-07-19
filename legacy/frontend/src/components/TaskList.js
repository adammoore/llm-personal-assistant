// src/components/TaskList.js

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Checkbox from '@mui/material/Checkbox';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import Fab from '@mui/material/Fab';
import AddIcon from '@mui/icons-material/Add';
import TextField from '@mui/material/TextField';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogContentText from '@mui/material/DialogContentText';
import DialogTitle from '@mui/material/DialogTitle';
import Button from '@mui/material/Button';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import InputLabel from '@mui/material/InputLabel';
import FormControl from '@mui/material/FormControl';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import IconButton from '@mui/material/IconButton'; // Import IconButton

const categories = [
  'Work',
  'Personal',
  'Health',
  'Finance',
  'Other',
];

const TaskList = () => {
  const [tasks, setTasks] = useState([]);
  const [newTask, setNewTask] = useState({ title: '', category: 'Other' });
  const [openDialog, setOpenDialog] = useState(false);
  const [editingTask, setEditingTask] = useState(null);
  const [showCompleted, setShowCompleted] = useState(true);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      const response = await axios.get('/api/tasks/');
      setTasks(response.data);
    } catch (error) {
      console.error('Error fetching tasks:', error);
    }
  };

  const handleCreateTask = async () => {
    try {
      const response = await axios.post('/api/tasks/', newTask);
      setTasks([...tasks, response.data]);
      setNewTask({ title: '', category: 'Other' });
      setOpenDialog(false);
    } catch (error) {
      console.error('Error creating task:', error);
    }
  };

  const handleUpdateTask = async (updatedTask) => {
    try {
      await axios.put(`/api/tasks/${updatedTask.id}/`, updatedTask);
      setTasks(tasks.map((task) => (task.id === updatedTask.id ? updatedTask : task)));
    } catch (error) {
      console.error('Error updating task:', error);
    }
  };

  const handleDeleteTask = async (taskId) => {
    try {
      await axios.delete(`/api/tasks/${taskId}/`);
      setTasks(tasks.filter((task) => task.id !== taskId));
    } catch (error) {
      console.error('Error deleting task:', error);
    }
  };

  const handleToggleComplete = (taskId) => {
    const updatedTasks = tasks.map((task) => {
      if (task.id === taskId) {
        return { ...task, completed: !task.completed };
      }
      return task;
    });
    setTasks(updatedTasks);
    // Update task completion status in the backend
    const updatedTask = updatedTasks.find((task) => task.id === taskId);
    handleUpdateTask(updatedTask);
  };

  const handleOpenEditDialog = (task) => {
    setEditingTask(task);
    setOpenDialog(true);
  };

  const handleCloseDialog = () => {
    setEditingTask(null);
    setOpenDialog(false);
  };

  const handleEditTask = () => {
    handleUpdateTask(editingTask);
    handleCloseDialog();
  };

  const handleChange = (event) => {
    setNewTask({ ...newTask, [event.target.name]: event.target.value });
  };

  const handleEditChange = (event) => {
    setEditingTask({ ...editingTask, [event.target.name]: event.target.value });
  };

  const handleShowCompletedChange = (event) => {
    setShowCompleted(event.target.checked);
  };

  return (
    <div>
      <FormControlLabel
        control={<Switch checked={showCompleted} onChange={handleShowCompletedChange} />}
        label="Show Completed Tasks"
      />

      {tasks
        .filter((task) => showCompleted || !task.completed)
        .map((task) => (
          <Accordion key={task.id}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls={`panel${task.id}-content`}
              id={`panel${task.id}-header`}
            >
              <Checkbox
                checked={task.completed}
                onChange={() => handleToggleComplete(task.id)}
                style={{ marginRight: '10px' }}
              />
              <Typography sx={{ flexGrow: 1 }}>{task.title}</Typography>
              <FormControl variant="standard" sx={{ minWidth: 120 }}>
                <InputLabel id={`category-label-${task.id}`}>Category</InputLabel>
                <Select
                  labelId={`category-label-${task.id}`}
                  id={`category-${task.id}`}
                  value={task.category}
                  onChange={(event) =>
                    handleUpdateTask({ ...task, category: event.target.value })
                  }
                  label="Category"
                >
                  {categories.map((category) => (
                    <MenuItem key={category} value={category}>
                      {category}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <IconButton onClick={() => handleOpenEditDialog(task)}>
                <EditIcon />
              </IconButton>
              <IconButton onClick={() => handleDeleteTask(task.id)}>
                <DeleteIcon />
              </IconButton>
            </AccordionSummary>
            <AccordionDetails>
              <Typography>
                {/* Add more task details here if needed */}
              </Typography>
            </AccordionDetails>
          </Accordion>
        ))}

      <Fab color="primary" aria-label="add" onClick={() => setOpenDialog(true)}>
        <AddIcon />
      </Fab>

      <Dialog open={openDialog} onClose={handleCloseDialog}>
        <DialogTitle>{editingTask ? 'Edit Task' : 'Create Task'}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {editingTask
              ? 'Edit the details of your task below.'
              : 'Enter the details of your new task below.'}
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            name="title"
            label="Task Title"
            type="text"
            fullWidth
            variant="standard"
            value={editingTask ? editingTask.title : newTask.title}
            onChange={editingTask ? handleEditChange : handleChange}
          />
          <FormControl variant="standard" sx={{ minWidth: 120, marginTop: '16px' }}>
            <InputLabel id="category-label">Category</InputLabel>
            <Select
              labelId="category-label"
              id="category"
              name="category"
              value={editingTask ? editingTask.category : newTask.category}
              onChange={editingTask ? handleEditChange : handleChange}
              label="Category"
            >
              {categories.map((category) => (
                <MenuItem key={category} value={category}>
                  {category}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button onClick={editingTask ? handleEditTask : handleCreateTask}>
            {editingTask ? 'Save' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </div>
  );
};

export default TaskList;