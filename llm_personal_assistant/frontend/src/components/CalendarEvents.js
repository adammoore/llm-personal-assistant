import React, { useState, useEffect } from 'react';
import { List, ListItem, ListItemText, Typography, TextField, Button } from '@mui/material';
import axios from 'axios';

const CalendarEvents = () => {
  const [events, setEvents] = useState([]);
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);
  const [authUrl, setAuthUrl] = useState('');

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    try {
      const response = await axios.get('http://localhost:8000/calendar/events', { withCredentials: true });
      if (response.data.events) {
        setEvents(response.data.events);
      } else if (response.data.auth_url) {
        setAuthUrl(response.data.auth_url);
      }
    } catch (error) {
      console.error('Error fetching calendar events:', error);
      if (error.response && error.response.status === 307) {
        setAuthUrl(error.response.headers.location);
      }
    }
  };

  const handleAuth = () => {
    window.location.href = authUrl;
  };

  const filteredEvents = events.filter(event => {
    const eventDate = new Date(event.start.dateTime).toISOString().split('T')[0];
    return eventDate === selectedDate;
  });

  if (authUrl) {
    return (
      <div>
        <Typography variant="h6" gutterBottom>
          Google Calendar Authentication Required
        </Typography>
        <Button variant="contained" color="primary" onClick={handleAuth}>
          Authenticate with Google Calendar
        </Button>
      </div>
    );
  }

  return (
    <div>
      <TextField
        type="date"
        value={selectedDate}
        onChange={(e) => setSelectedDate(e.target.value)}
        sx={{ mb: 2, width: '100%' }}
      />
      <Typography variant="h6" gutterBottom>
        Events for {new Date(selectedDate).toDateString()}
      </Typography>
      <List>
        {filteredEvents.map((event, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={event.summary}
              secondary={`${new Date(event.start.dateTime).toLocaleTimeString()} - ${new Date(event.end.dateTime).toLocaleTimeString()}`}
            />
          </ListItem>
        ))}
      </List>
    </div>
  );
};

export default CalendarEvents;