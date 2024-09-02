import React, { useState, useEffect } from 'react';
import { List, ListItem, ListItemText, Typography } from '@material-ui/core';
import axios from 'axios';

const CalendarEvents = () => {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    try {
      const response = await axios.get('http://localhost:8000/calendar/events');
      setEvents(response.data.events);
    } catch (error) {
      console.error('Error fetching calendar events:', error);
    }
  };

  return (
    <div>
      <Typography variant="h4" component="h2">
        Upcoming Events
      </Typography>
      <List>
        {events.map((event, index) => (
          <ListItem key={index}>
            <ListItemText
              primary={event.summary}
              secondary={`${new Date(event.start.dateTime).toLocaleString()} - ${new Date(event.end.dateTime).toLocaleString()}`}
            />
          </ListItem>
        ))}
      </List>
    </div>
  );
};

export default CalendarEvents;