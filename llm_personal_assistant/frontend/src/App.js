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
import DailyPrompt from './components/DailyPrompt';
import TaskList from './components/TaskList';
import AddTaskModal from './components/AddTaskModal';
import CalendarEvents from './components/CalendarEvents';
import AIAutonomyDialog from './components/AIAutonomyDialog';
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
            <IconButton color="inherit" onClick={() => setGeneralSettingsOpen(true)}>
              <SettingsIcon />
            </IconButton>
          </Toolbar>
        </AppBar>
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4, flexGrow: 1 }}>
          <Grid container spacing={4}>
            <Grid item xs={12} md={8}>
              <Paper sx={{ mb: 4 }}>
                <Typography variant="h5" component="h2" gutterBottom>
                  Daily Prompt
                </Typography>
                <DailyPrompt />
              </Paper>
              <Paper>
                <Typography variant="h5" component="h2" gutterBottom>
                  Tasks
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
                <CalendarEvents />
              </Paper>
            </Grid>
          </Grid>
        </Container>
      </Box>
      <AIAutonomyDialog
        open={aiAutonomyDialogOpen}
        onClose={() => setAiAutonomyDialogOpen(false)}
        onSave={(autonomy) => {
          setAiAutonomy(autonomy);
        }}
        initialAutonomy={aiAutonomy}
      />
      <GeneralSettings
        open={generalSettingsOpen}
        onClose={() => setGeneralSettingsOpen(false)}
        darkMode={darkMode}
        setDarkMode={setDarkMode}
        highContrast={highContrast}
        setHighContrast={setHighContrast}
        onResetAuth={handleResetAuth}
      />
    </ThemeProvider>
  );
};

export default App;