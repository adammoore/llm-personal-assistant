import React, { useState } from 'react';
import { Dialog, DialogTitle, DialogContent, DialogActions, Button, Switch, FormControlLabel } from '@mui/material';
import axios from 'axios';

const AIAutonomyDialog = ({ open, onClose, onSave, initialAutonomy }) => {
  const [autonomy, setAutonomy] = useState(initialAutonomy);

  const handleSave = async () => {
    try {
      await axios.post('http://localhost:8000/ai-autonomy', { autonomous: autonomy });
      onSave(autonomy);
      onClose();
    } catch (error) {
      console.error('Error saving AI autonomy setting:', error);
    }
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>AI Autonomy Settings</DialogTitle>
      <DialogContent>
        <FormControlLabel
          control={
            <Switch
              checked={autonomy}
              onChange={(e) => setAutonomy(e.target.checked)}
            />
          }
          label="Allow AI to act autonomously"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSave}>Save</Button>
      </DialogActions>
    </Dialog>
  );
};

export default AIAutonomyDialog;