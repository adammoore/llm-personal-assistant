#!/bin/bash

# Start the backend
echo "Starting backend..."
cd backend || exit
source .venv/bin/activate
uvicorn main:app --reload &

# Start the frontend
echo "Starting frontend..."
cd ../frontend || exit
npm start