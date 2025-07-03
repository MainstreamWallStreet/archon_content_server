# Archon Content Server API Documentation

## Overview

The Archon Content Server is a streamlined FastAPI application that provides two core functionalities:

1. **LangFlow Research Integration** - Execute research flows via external LangFlow server
2. **Spreadsheet Generation** - Create Excel workbooks from natural language descriptions

## Base URL

- **Local Development**: `http://localhost:8080`
- **Production**: `https://your-domain.com`

## Authentication

All endpoints require authentication using an API key header:

```
X-API-Key: your-secret-api-key
```

## Environment Variables

| Variable | Description | Required | Example |
|:---|:---|:---|:---|
| `ARCHON_API_KEY` | Authentication key for the API | Yes | `your-secret-api-key` |
| `LANGFLOW_SERVER_URL` | Base URL for LangFlow server | Yes* | `http://0.0.0.0:7860/api/v1/run/` |
| `LANGFLOW_API_KEY` | API key for LangFlow server | Yes* | `your-langflow-key` |
| `OPENAI_API_KEY` | OpenAI API key for LLM plan generation | Yes* | `sk-...` |

*Required only for the respective functionality (research or spreadsheet generation)

---

## Endpoints

### 1. Health Check

**GET** `/health`

Check if the service is running and healthy.

#### Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00.000000+00:00",
  "version": "1.0.0"
}
```

#### Example

```bash
curl -X GET "http://localhost:8080/health" \
  -H "X-API-Key: your-secret-api-key"
```

---

### 2. Research Endpoint

**POST** `/research`

Execute a research flow on the external LangFlow server.

#### Request Body

```json
{
  "query": "How should we think about risk?",
  "flow_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51"
}
```

| Field | Type | Required | Description |
|:---|:---|:---|:---|
| `query` | string | Yes | The research question or query to send to LangFlow |
| `flow_id` | string | Yes | The LangFlow flow ID to execute |

#### Response

```json
{
  "result": "How We Think About Risk\n\n1. The working definition of risk..."
}
```

#### Example

```bash
curl -X POST "http://localhost:8080/research" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How should we think about risk?",
    "flow_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51"
  }'
```

#### Error Responses

- **503 Service Unavailable**: Missing LangFlow configuration
- **500 Internal Server Error**: LangFlow server error
- **422 Validation Error**: Invalid request body

---

### 3. Spreadsheet Build Endpoint

**POST** `/spreadsheet/build`

Generate an Excel workbook from a natural language description.

#### Request Body

```json
{
  "objective": "Model FY-2024 revenue break-even analysis",
  "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%"
}
```

| Field | Type | Required | Description |
|:---|:---|:---|:---|
| `objective` | string | Yes | What to model (passed to OpenAI) |
| `data` | string | No | Plaintext data or `@/abs/path.txt` to read from file |

#### Response

Returns an Excel file (`.xlsx`) as a download.

#### Example

```bash
curl -X POST "http://localhost:8080/spreadsheet/build" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Model FY-2024 revenue break-even analysis",
    "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%"
  }' \
  --output "financial_model.xlsx"
```

#### Error Responses

- **503 Service Unavailable**: Missing OpenAI API key
- **500 Internal Server Error**: Plan generation or Excel build error
- **422 Validation Error**: Invalid request body

---

### 4. Spreadsheet Plan Endpoint

**POST** `/spreadsheet/plan`

Generate just the build plan JSON without creating the Excel file.

#### Request Body

Same as `/spreadsheet/build` endpoint.

#### Response

```json
{
  "workbook": {
    "filename": "financial_model.xlsx"
  },
  "worksheet": {
    "name": "Model",
    "columns": [
      {
        "name": "Revenue",
        "type": "number",
        "format": "currency"
      }
    ]
  }
}
```

#### Example

```bash
curl -X POST "http://localhost:8080/spreadsheet/plan" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Model FY-2024 revenue break-even analysis",
    "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%"
  }'
```

#### Error Responses

- **503 Service Unavailable**: Missing OpenAI API key
- **500 Internal Server Error**: Plan generation error
- **422 Validation Error**: Invalid request body

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

- **200 OK**: Request successful
- **422 Unprocessable Entity**: Validation error (missing required fields, invalid data types)
- **500 Internal Server Error**: Server-side error
- **503 Service Unavailable**: Missing configuration or external service unavailable

---

## Rate Limiting

Currently, no rate limiting is implemented. Consider implementing rate limiting for production use.

---

## CORS

CORS is not configured by default. For web applications, you may need to configure CORS headers.

---

## Examples

### Complete Research Workflow

```bash
# 1. Check service health
curl -X GET "http://localhost:8080/health" \
  -H "X-API-Key: your-secret-api-key"

# 2. Execute research query
curl -X POST "http://localhost:8080/research" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key factors for startup success?",
    "flow_id": "your-langflow-flow-id"
  }'
```

### Complete Spreadsheet Workflow

```bash
# 1. Generate plan preview
curl -X POST "http://localhost:8080/spreadsheet/plan" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Create a startup financial model",
    "data": "Initial funding: 500K, Monthly burn: 50K, Revenue growth: 20%"
  }'

# 2. Generate Excel file
curl -X POST "http://localhost:8080/spreadsheet/build" \
  -H "X-API-Key: your-secret-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "objective": "Create a startup financial model",
    "data": "Initial funding: 500K, Monthly burn: 50K, Revenue growth: 20%"
  }' \
  --output "startup_model.xlsx"
```

---

## SDK Examples

### Python

```python
import requests

BASE_URL = "http://localhost:8080"
API_KEY = "your-secret-api-key"
HEADERS = {"X-API-Key": API_KEY}

# Health check
response = requests.get(f"{BASE_URL}/health", headers=HEADERS)
print(response.json())

# Research query
research_data = {
    "query": "Explain quantum computing",
    "flow_id": "your-flow-id"
}
response = requests.post(f"{BASE_URL}/research", 
                        json=research_data, 
                        headers=HEADERS)
print(response.json()["result"])

# Generate spreadsheet
spreadsheet_data = {
    "objective": "Model quarterly revenue",
    "data": "Q1: 100K, Q2: 150K, Q3: 200K"
}
response = requests.post(f"{BASE_URL}/spreadsheet/build", 
                        json=spreadsheet_data, 
                        headers=HEADERS)
with open("revenue_model.xlsx", "wb") as f:
    f.write(response.content)
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8080';
const API_KEY = 'your-secret-api-key';
const headers = { 'X-API-Key': API_KEY };

// Health check
async function checkHealth() {
  const response = await axios.get(`${BASE_URL}/health`, { headers });
  console.log(response.data);
}

// Research query
async function research(query, flowId) {
  const response = await axios.post(`${BASE_URL}/research`, {
    query,
    flow_id: flowId
  }, { headers });
  return response.data.result;
}

// Generate spreadsheet
async function generateSpreadsheet(objective, data) {
  const response = await axios.post(`${BASE_URL}/spreadsheet/build`, {
    objective,
    data
  }, { 
    headers,
    responseType: 'stream'
  });
  
  const fs = require('fs');
  const writer = fs.createWriteStream('model.xlsx');
  response.data.pipe(writer);
}
```

---

## Troubleshooting

### Common Issues

1. **503 Service Unavailable**
   - Check that required environment variables are set
   - Verify LangFlow server is running and accessible
   - Ensure OpenAI API key is valid

2. **422 Validation Error**
   - Check request body format
   - Ensure all required fields are present
   - Verify data types match expected format

3. **500 Internal Server Error**
   - Check application logs for detailed error messages
   - Verify external services (LangFlow, OpenAI) are responding
   - Ensure sufficient disk space for temporary files

### Debug Mode

To enable debug logging, set the environment variable:

```bash
export LOG_LEVEL=DEBUG
```

---

## Support

For issues and questions:

1. Check the application logs for detailed error messages
2. Verify all environment variables are correctly configured
3. Test external service connectivity
4. Review the troubleshooting section above

---

## Version History

- **v1.0.0**: Initial release with LangFlow integration and spreadsheet generation 