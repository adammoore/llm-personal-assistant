import React, { useState, useEffect } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import Box from '@mui/material/Box';
import AppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import Typography from '@mui/material/Typography';
import Container from '@mui/material/Container';
import Grid from '@mui/material/Grid';
import Paper from '@mui/material/Paper';
import IconButton from '@mui/material/IconButton';
import SettingsIcon from '@mui/icons-material/Settings';
import Tooltip from '@mui/material/Tooltip';
import DailyPrompt from './components/DailyPrompt';
import TaskList from './components/TaskList';
import AddTaskModal from './components/AddTaskModal';
import CalendarEvents from './components/CalendarEvents';
import GeneralSettings from './components/GeneralSettings';
import axios from 'axios';

const App = () => {
  const [darkMode, setDarkMode] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [aiAutonomyDialogOpen, setAiAutonomyDialogOpen] = useState(false);
  const [generalSettingsOpen, setGeneralSettingsOpen] = useState(false);
  const [aiAutonomy, setAiAutonomy] = useState(false);

  useEffect(() => {
    // Fetch initial AI autonomy setting
    const fetchAIAutonomy = async () => {
      try {
        const response = await axios.get('http://localhost:8000/ai-autonomy');
        setAiAutonomy(response.data.autonomous);
      } catch (error) {
        console.error('Error fetching AI autonomy setting:', error);
      }
    };
    fetchAIAutonomy();
  }, []);

  const handleResetAuth = async () => {
    try {
      await axios.post('http://localhost:8000/reset-auth');
      alert('Authentication has been reset. Please re-authenticate.');
    } catch (error) {
      console.error('Error resetting authentication:', error);
      alert('Failed to reset authentication. Please try again.');
    }
  };

  const handleSetAIAutonomy = async (value) => {
    try {
      await axios.post('http://localhost:8000/ai-autonomy', { autonomous: value });
      setAiAutonomy(value);
    } catch (error) {
      console.error('Error setting AI autonomy:', error);
      alert('Failed to set AI autonomy. Please try again.');
    }
  };

  const theme = createTheme({
    palette: {
      mode: darkMode ? 'dark' : 'light',
      primary: {
        main: '#2e7d32',
      },
      secondary: {
        main: '#81c784',
      },
      background: {
        default: darkMode ? '#121212' : '#e8f5e9',
        paper: darkMode ? '#1e1e1e' : '#ffffff',
      },
      text: {
        primary: darkMode ? '#ffffff' : '#33691e',
      },
    },
    typography: {
      fontSize: 16,
    },
    components: {
      MuiPaper: {
        styleOverrides: {
          root: {
            padding: '24px',
            marginBottom: '24px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            textTransform: 'none',
          },
        },
      },
    },
  });

  if (highContrast) {
    theme.palette.background.default = '#ffffff';
    theme.palette.background.paper = '#e0e0e0';
    theme.palette.text.primary = '#000000';
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
        <AppBar position="static">
          <Toolbar>
            <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
              LLM Personal Assistant
            </Typography>
            <Tooltip title="Open settings">
              <IconButton color="inherit" onClick={() => setGeneralSettingsOpen(true)}>
                <SettingsIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
          <Grid container spacing={4}>
            <Grid item xs={12} md={8}>
              <Paper sx={{ mb: 4 }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  Daily Prompt
                </Typography>
                <Typography variant="body2" gutterBottom>
                  Reflect on your day and set your intentions with the daily prompt.
                </Typography>
                <DailyPrompt />
              </Paper>
              <Paper>
                <Typography variant="h5" component="h2" gutterBottom>
                  Tasks
                </Typography>
                <Typography variant="body2" gutterBottom>
                  Manage your tasks efficiently. Click on a task to expand details.
                </Typography>
                <TaskList />
                <Box sx={{ mt: 2 }}>
                  <AddTaskModal />
                </Box>
              </Paper>
            </Grid>
            <Grid item xs={12} md={4}>
              <Paper>
                <Typography variant="h5" component="h2" gutterBottom>
                  Upcoming Events
                </Typography>
                <Typography variant="body2" gutterBottom>
                  Stay on top of your schedule with upcoming events from your calendar.
                </Typography>
                <CalendarEvents />
              </Paper>
            </Grid>
          </Grid>
        </Container>
        <Box component="footer" sx={{ mt: 'auto', py: 2, bgcolor: 'background.paper' }}>
          <Container maxWidth="lg">
            <Typography variant="body2" color="text.secondary" align="center">
              LLM Personal Assistant v1.0.0 | Created by Adam Vials Moore
            </Typography>
          </Container>
        </Box>
      </Box>
      <GeneralSettings
        open={generalSettingsOpen}
        onClose={() => setGeneralSettingsOpen(false)}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        highContrast={highContrast}
        setHighContrast={setHighContrast}
        aiAutonomy={aiAutonomy}
        setAiAutonomy={setAiAutonomy}
      />
    </ThemeProvider>
  );
};

export default App;