#!/bin/bash

API_KEY=$(grep BANSHEE_API_KEY .env | cut -d "=" -f2)

# Test root endpoint
echo "Testing root endpoint..."
curl -v http://localhost:8000/

# Test watchlist endpoints
echo -e "
Testing watchlist endpoints..."
curl -v -H "X-API-Key: $API_KEY" http://localhost:8000/watchlist

# Test adding a ticker
echo -e "
Testing add ticker..."
curl -v -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" -d '{"ticker":"AAPL","user":"test"}' http://localhost:8000/watchlist

# Test upcoming earnings
echo -e "
Testing upcoming earnings..."
curl -v -H "X-API-Key: $API_KEY" http://localhost:8000/earnings/upcoming

# Test specific ticker earnings
echo -e "
Testing specific ticker earnings..."
curl -v -H "X-API-Key: $API_KEY" http://localhost:8000/earnings/AAPL

# Test daily sync
echo -e "
Testing daily sync..."
curl -v -H "X-API-Key: $API_KEY" -X POST http://localhost:8000/tasks/daily-sync

# Test upcoming sync
echo -e "
Testing upcoming sync..."
curl -v -H "X-API-Key: $API_KEY" -X POST http://localhost:8000/tasks/upcoming-sync

# Test send queued emails
echo -e "
Testing send queued emails..."
curl -v -H "X-API-Key: $API_KEY" -X POST http://localhost:8000/tasks/send-queued-emails

# Test test email
echo -e "
Testing test email..."
curl -v -H "X-API-Key: $API_KEY" -X POST "http://localhost:8000/test-email?to=gclark0812@gmail.com"
