import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Switch, FormControlLabel, Typography, Tooltip } from '@mui/material';
import axios from 'axios';

const GeneralSettings = ({ open, onClose, darkMode, setDarkMode, highContrast, setHighContrast, aiAutonomy, setAiAutonomy }) => {
  const handleResetAuth = async () => {
    try {
      await axios.get('http://localhost:3000/refresh_calendar_auth');
      alert('Calendar authentication has been reset. Please re-authenticate.');
    } catch (error) {
      console.error('Error resetting calendar authentication:', error);
      alert('Failed to reset calendar authentication. Please try again.');
    }
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>General Settings</DialogTitle>
      <DialogContent>
        <Tooltip title="Toggle dark mode for a darker color scheme">
          <FormControlLabel
            control={<Switch checked={darkMode} onChange={() => setDarkMode(!darkMode)} />}
            label="Dark Mode"
          />
        </Tooltip>
        <Tooltip title="Enable high contrast mode for better visibility">
          <FormControlLabel
            control={<Switch checked={highContrast} onChange={() => setHighContrast(!highContrast)} />}
            label="High Contrast"
          />
        </Tooltip>
        <Tooltip title="Allow AI to make autonomous decisions">
          <FormControlLabel
            control={<Switch checked={aiAutonomy} onChange={() => setAiAutonomy(!aiAutonomy)} />}
            label="AI Autonomy"
          />
        </Tooltip>
        <Typography variant="body1" sx={{ mt: 2 }}>
          Calendar Authentication:
        </Typography>
        <Tooltip title="Reset your Google Calendar authentication">
          <Button variant="outlined" onClick={handleResetAuth} sx={{ mt: 1 }}>
            Reset Calendar Authentication
          </Button>
        </Tooltip>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default GeneralSettings;