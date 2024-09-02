import React, { useState, useEffect } from 'react';
import { List, ListItem, ListItemText, Typography, Tooltip, Button } from '@mui/material';
import axios from 'axios';

const CalendarEvents = () => {
  const [events, setEvents] = useState([]);
  const [isAuthenticated, setIsAuthenticated] = useState(true);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    try {
      const response = await axios.get('http://localhost:8000/calendar/events', { withCredentials: true });
      setEvents(response.data.events);
      setIsAuthenticated(true);
    } catch (error) {
      console.error('Error fetching calendar events:', error);
      if (error.response && error.response.status === 307) {
        window.location.href = error.response.headers.location;
      } else {
        setIsAuthenticated(false);
      }
    }
  };

  const handleAuthenticate = () => {
    window.location.href = 'http://localhost:8000/calendar/events';
  };

  if (!isAuthenticated) {
    return (
      <div>
        <Typography variant="h6" component="h2" gutterBottom>
          Google Calendar Authentication Required
        </Typography>
        <Button variant="contained" color="primary" onClick={handleAuthenticate}>
          Authenticate with Google Calendar
        </Button>
      </div>
    );
  }

  return (
    <div>
      <Typography variant="h6" component="h2" gutterBottom>
        Upcoming Events
      </Typography>
      <List>
        {events.map((event, index) => (
          <Tooltip key={index} title={`From ${new Date(event.start.dateTime).toLocaleString()} to ${new Date(event.end.dateTime).toLocaleString()}`}>
            <ListItem>
              <ListItemText
                primary={event.summary}
                secondary={new Date(event.start.dateTime).toLocaleDateString()}
              />
            </ListItem>
          </Tooltip>
        ))}
      </List>
    </div>
  );
};

export default CalendarEvents;