#!/bin/bash

# Configuration
LOCAL_API_URL="http://localhost:8080"
PROD_API_URL="https://filing-fetcher-api-455624753981.us-central1.run.app"
API_KEY=""
PROD_MODE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prod)
            PROD_MODE=true
            shift
            ;;
        -k)
            API_KEY="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--prod] [-k API_KEY]"
            exit 1
            ;;
    esac
done

# Set API URL based on mode
if [ "$PROD_MODE" = true ]; then
    API_URL="$PROD_API_URL"
    echo "🔧 Running in PRODUCTION mode"
else
    API_URL="$LOCAL_API_URL"
    echo "🔧 Running in LOCAL mode"
fi

# If API key not provided via flag, try environment variable
if [ -z "$API_KEY" ]; then
    API_KEY="${FFS_API_KEY}"
fi

# If still no API key, prompt the user
if [ -z "$API_KEY" ]; then
    echo -n "Please enter your API key: "
    read -s API_KEY
    echo  # New line after password input
fi

# Final check if API key is set
if [ -z "$API_KEY" ]; then
    echo "Error: No API key provided. Use -k flag or set FFS_API_KEY environment variable."
    exit 1
fi

# Function to queue a job
queue_job() {
    local year=$1
    local quarter=$2
    
    echo "Queueing job for AAPL - Year: $year, Quarter: $quarter"
    
    curl -s -X POST "${API_URL}/process" \
        -H "X-API-Key: ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "{
            \"ticker\": \"AAPL\",
            \"year\": ${year},
            \"quarter\": ${quarter},
            \"include_transcript\": true,
            \"point_of_origin\": \"queue_aapl_jobs\"
        }" | jq '.'
    
    # Add a small delay between requests to avoid overwhelming the server
    sleep 1
}

# Queue jobs for each year and quarter
for year in {2020..2024}; do
    for quarter in {1..4}; do
        queue_job $year $quarter
    done
done

echo "All jobs have been queued. Monitoring job statuses at ${API_URL}/updates (Ctrl+C to quit)"

# Function to fetch job statuses with retries
fetch_job_status() {
    local retries=3
    local delay=2
    local attempt=1
    
    while [ $attempt -le $retries ]; do
        local response=$(curl -s -w "\n%{http_code}" -X GET "${API_URL}/updates" \
            -H "X-API-Key: ${API_KEY}")
        
        local status_code=$(echo "$response" | tail -n1)
        local body=$(echo "$response" | sed '$d')
        
        if [ "$status_code" = "200" ]; then
            echo "$body"
            return 0
        elif [ "$status_code" = "503" ] || [ "$status_code" = "500" ]; then
            # Parse and display detailed error information
            local error_type=$(echo "$body" | jq -r '.error // "UNKNOWN_ERROR"')
            local error_msg=$(echo "$body" | jq -r '.message // "No error message"')
            local timestamp=$(echo "$body" | jq -r '.context.timestamp // "unknown"')
            
            echo "⚠️  Error (attempt $attempt/$retries):" >&2
            echo "   Type: $error_type" >&2
            echo "   Message: $error_msg" >&2
            echo "   Time: $timestamp" >&2
            
            # Display additional context if available
            if echo "$body" | jq -e '.context' >/dev/null 2>&1; then
                echo "   Context:" >&2
                echo "$body" | jq -r '.context | to_entries | .[] | "      \(.key): \(.value)"' >&2
            fi
            
            echo "   Retrying in ${delay}s..." >&2
            sleep $delay
            delay=$((delay * 2))
            attempt=$((attempt + 1))
        else
            echo "❌ Error fetching job status (HTTP $status_code)" >&2
            echo "Response: $body" >&2
            return 1
        fi
    done
    
    echo "❌ Failed to fetch job status after $retries attempts" >&2
    return 1
}

# Poll /updates every 10 seconds until interrupted
while true; do
    echo -e "\n📊 Job Statuses (as of $(date)) ---"
    fetch_job_status | jq -r '
        ["🆔 Job ID","📈 Status","📅 Year","Q","⏰ Received","▶️ Started","✅ Completed","📄 Transcript","🔍 Origin"],
        ((.user_requested_jobs // [])[] | [
            .job_id,
            (if .status == "queued" then "⏳ Queued"
             elif .status == "processing" then "🔄 Processing"
             elif .status == "completed" then "✅ Completed"
             elif .status == "failed" then "❌ Failed"
             else .status end),
            .request.year,
            .request.quarter,
            (.time_received // "-"),
            (.time_started // "-"),
            (.time_completed // "-"),
            (.transcript_url // "-"),
            (.point_of_origin // "unknown")
        ]) | @tsv' | column -t
    sleep 10
done 