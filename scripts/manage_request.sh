#!/bin/bash

# Request Management Script for FastAPI Server Template
# This script helps manage the request workflow for AI agents

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
REQUEST_ARCHIVE="$PROJECT_ROOT/docs/request-archive"
TEMPLATE_FILE="$REQUEST_ARCHIVE/request_template.md"
CURRENT_REQUEST="$PROJECT_ROOT/current_request.md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Function to create a new request
create_new_request() {
    print_header "Creating New Request"
    
    if [ -f "$CURRENT_REQUEST" ]; then
        print_warning "A current request already exists: $CURRENT_REQUEST"
        read -p "Do you want to archive it first? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            archive_current_request
        else
            print_error "Cannot create new request while one exists. Please archive the current request first."
            exit 1
        fi
    fi
    
    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_error "Template file not found: $TEMPLATE_FILE"
        exit 1
    fi
    
    cp "$TEMPLATE_FILE" "$CURRENT_REQUEST"
    print_status "New request created: $CURRENT_REQUEST"
    print_status "Please fill out the request details and save the file."
}

# Function to archive the current request
archive_current_request() {
    print_header "Archiving Current Request"
    
    if [ ! -f "$CURRENT_REQUEST" ]; then
        print_error "No current request found: $CURRENT_REQUEST"
        exit 1
    fi
    
    # Generate timestamp for filename
    TIMESTAMP=$(date +"%Y-%m-%d-%H%M")
    
    # Extract request ID from the file or generate one
    REQUEST_ID=$(grep -o 'REQ-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}-[0-9]\{4\}' "$CURRENT_REQUEST" 2>/dev/null || echo "REQ-$TIMESTAMP")
    
    # Extract description from the file or use default
    DESCRIPTION=$(grep -A 1 "Primary Request" "$CURRENT_REQUEST" | tail -n 1 | sed 's/^\[//;s/\]$//' | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/_/g' | sed 's/__*/_/g' | sed 's/^_//;s/_$//')
    if [ -z "$DESCRIPTION" ] || [ "$DESCRIPTION" = "describe_the_main_request_or_feature_needed" ]; then
        DESCRIPTION="request"
    fi
    
    ARCHIVE_FILENAME="$REQUEST_ARCHIVE/REQ-$TIMESTAMP-$DESCRIPTION.md"
    
    # Move current request to archive
    mv "$CURRENT_REQUEST" "$ARCHIVE_FILENAME"
    print_status "Request archived: $ARCHIVE_FILENAME"
    
    # Create new blank request
    cp "$TEMPLATE_FILE" "$CURRENT_REQUEST"
    print_status "New blank request created: $CURRENT_REQUEST"
}

# Function to list archived requests
list_archived_requests() {
    print_header "Archived Requests"
    
    if [ ! -d "$REQUEST_ARCHIVE" ]; then
        print_error "Request archive directory not found: $REQUEST_ARCHIVE"
        exit 1
    fi
    
    # Find all archived request files (excluding template and README)
    ARCHIVED_REQUESTS=$(find "$REQUEST_ARCHIVE" -name "REQ-*.md" -type f | sort)
    
    if [ -z "$ARCHIVED_REQUESTS" ]; then
        print_status "No archived requests found."
        return
    fi
    
    echo "Archived requests:"
    echo
    for request in $ARCHIVED_REQUESTS; do
        filename=$(basename "$request")
        echo "  - $filename"
        
        # Extract and display basic info
        if [ -f "$request" ]; then
            echo "    Date: $(grep -o '[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}' "$request" | head -1)"
            echo "    Status: $(grep -A 1 "Status" "$request" | tail -n 1 | sed 's/^\[//;s/\]$//')"
            echo "    Primary Request: $(grep -A 1 "Primary Request" "$request" | tail -n 1 | sed 's/^\[//;s/\]$//')"
            echo
        fi
    done
}

# Function to show current request status
show_current_status() {
    print_header "Current Request Status"
    
    if [ ! -f "$CURRENT_REQUEST" ]; then
        print_status "No current request found."
        return
    fi
    
    echo "Current request: $CURRENT_REQUEST"
    echo
    
    # Extract and display key information
    if [ -f "$CURRENT_REQUEST" ]; then
        echo "Request ID: $(grep -o 'REQ-[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}-[0-9]\{4\}' "$CURRENT_REQUEST" 2>/dev/null || echo 'Not set')"
        echo "Date Created: $(grep -o '[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}' "$CURRENT_REQUEST" | head -1 || echo 'Not set')"
        echo "Status: $(grep -A 1 "Status" "$CURRENT_REQUEST" | tail -n 1 | sed 's/^\[//;s/\]$//' || echo 'Not set')"
        echo "Primary Request: $(grep -A 1 "Primary Request" "$CURRENT_REQUEST" | tail -n 1 | sed 's/^\[//;s/\]$//' || echo 'Not set')"
    fi
}

# Function to show help
show_help() {
    print_header "Request Management Script Help"
    echo
    echo "Usage: $0 [COMMAND]"
    echo
    echo "Commands:"
    echo "  new          Create a new request (archives current if exists)"
    echo "  archive      Archive the current request and create a new blank one"
    echo "  list         List all archived requests"
    echo "  status       Show current request status"
    echo "  help         Show this help message"
    echo
    echo "Examples:"
    echo "  $0 new       # Create a new request"
    echo "  $0 archive   # Archive current request"
    echo "  $0 list      # List archived requests"
    echo "  $0 status    # Show current status"
}

# Main script logic
case "${1:-help}" in
    "new")
        create_new_request
        ;;
    "archive")
        archive_current_request
        ;;
    "list")
        list_archived_requests
        ;;
    "status")
        show_current_status
        ;;
    "help"|"--help"|"-h")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac 