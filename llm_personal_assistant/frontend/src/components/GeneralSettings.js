import React from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Switch, FormControlLabel, Typography } from '@mui/material';

const GeneralSettings = ({ open, onClose, darkMode, setDarkMode, highContrast, setHighContrast, onResetAuth }) => {
  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>General Settings</DialogTitle>
      <DialogContent>
        <FormControlLabel
          control={<Switch checked={darkMode} onChange={() => setDarkMode(!darkMode)} />}
          label="Dark Mode"
        />
        <FormControlLabel
          control={<Switch checked={highContrast} onChange={() => setHighContrast(!highContrast)} />}
          label="High Contrast"
        />
        <Typography variant="body1" sx={{ mt: 2 }}>
          Authentication:
        </Typography>
        <Button variant="outlined" onClick={onResetAuth} sx={{ mt: 1 }}>
          Reset Authentication / Switch Account
        </Button>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default GeneralSettings;