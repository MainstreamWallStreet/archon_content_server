# Archon Content Server

A streamlined FastAPI application focused on two core functionalities:
1. **LangFlow Integration** - Execute research flows via external LangFlow server
2. **Spreadsheet Building** - Generate Excel workbooks from natural language descriptions

## Features

- **LangFlow Research** – Execute external LangFlow flows and extract clean text responses
- **Spreadsheet Generation** – Create Excel workbooks from natural language using OpenAI
- **FastAPI Framework** – Modern web framework with automatic OpenAPI docs
- **Authentication** – Simple header-based API-key auth (`ARCHON_API_KEY`)
- **Comprehensive Testing** – Full test suite covering all endpoints
- **Production Ready** – Structured logging, error handling, health checks

## Project Structure

```
archon_content_server/
├── src/                    # Application source code
│   ├── api.py             # All API endpoints (consolidated)
│   ├── config.py          # Configuration management
│   └── spreadsheet_builder/ # Spreadsheet generation module
│       ├── __init__.py    # Package init
│       ├── builder.py     # Excel workbook builder
│       ├── cli.py         # Command-line interface
│       ├── llm_plan_builder.py # LLM plan generation
│       ├── spec.py        # Data specifications
│       └── README.md      # Module documentation
├── tests/                 # Test suite
│   ├── conftest.py        # Pytest configuration and fixtures
│   ├── test_config.py     # Configuration tests
│   ├── test_research.py   # Research endpoint tests
│   ├── test_spreadsheet_api.py # Spreadsheet API tests
│   └── test_spreadsheet_builder.py # Spreadsheet builder tests
├── infra/                 # Infrastructure as Code
├── docs/                  # Documentation
├── scripts/              # Utility scripts
├── requirements.txt      # Python dependencies
├── pyproject.toml        # Project configuration
├── Dockerfile           # Container configuration
├── run.py               # Application entry point
└── README.md            # This file
```

## Quick Start

1. **Clone and setup:**
   ```sh
   git clone <repo-url>
   cd archon_content_server
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```sh
   cp sample.env .env
   # Edit .env with your configuration
   ```

3. **Run locally:**
   ```sh
   python run.py
   ```

4. **Access API:**
   - API: http://localhost:8080
   - Documentation: http://localhost:8080/docs
   - Health Check: http://localhost:8080/health

## Environment Variables

| Variable | Description | Required | Example |
|:---|:---|:---|:---|
| `ARCHON_API_KEY` | Authentication key for the API | Yes | `your-secret-api-key` |
| `LANGFLOW_SERVER_URL` | Base URL for LangFlow server | Yes* | `http://0.0.0.0:7860/api/v1/run/` |
| `LANGFLOW_API_KEY` | API key for LangFlow server | Yes* | `your-langflow-key` |
| `OPENAI_API_KEY` | OpenAI API key for LLM plan generation | Yes* | `sk-...` |

*Required only for the respective functionality (research or spreadsheet generation)

## API Endpoints

### Authentication
All endpoints require an `X-API-Key` header with your configured API key.

### Core Endpoints

- `GET /health` - Health check with service status and timestamp

### Research Endpoints

- `POST /research` - Execute a LangFlow research flow
  ```json
  {
    "query": "How should we think about risk?",
    "flow_id": "af41bf0f-6ffb-4591-a276-8ae5f296da51"
  }
  ```

### Spreadsheet Endpoints

- `POST /spreadsheet/build` - Generate Excel workbook from natural language
  ```json
  {
    "objective": "Model FY-2024 revenue break-even analysis",
    "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%"
  }
  ```

- `POST /spreadsheet/plan` - Generate build plan JSON only (preview)
  ```json
  {
    "objective": "Model FY-2024 revenue break-even analysis",
    "data": "Revenue: 763.9M, Fixed Costs: 45M, Variable Cost %: 12%"
  }
  ```

## Development

### Running Tests
```sh
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_research.py
```

### Code Quality
```sh
# Type checking
mypy src/

# Linting
flake8 src/

# Formatting
black src/
```

### Local Development
```sh
# Start with hot reload
python run.py

# Start with Docker
docker build -t archon-content-server .
docker run -p 8080:8080 archon-content-server
```

## Deployment

### Infrastructure Setup
```sh
cd infra
terraform init
terraform plan
terraform apply
```

### CI/CD Pipeline
The application includes:
- **GitHub Actions**: Automated testing and deployment
- **Cloud Build**: Automated Docker image building
- **Cloud Run**: Direct deployment with health verification

### Manual Deployment
```sh
# Test deployment script
./scripts/test_deployment.sh

# Direct Cloud Run deployment
gcloud run deploy archon-content-api \
  --image=us-central1-docker.pkg.dev/your-project/archon-content/archon-content:latest \
  --region=us-central1 \
  --platform=managed
```

## Architecture

### Core Components

- **API Layer**: FastAPI application with consolidated endpoints
- **Configuration**: Environment and secret management
- **Spreadsheet Builder**: Excel workbook generation from LLM plans

### Data Flow

1. **Research Flow**: Query → LangFlow Server → Extract Answer → Return Text
2. **Spreadsheet Flow**: Objective → OpenAI → Build Plan → Excel File → Download

## Documentation

- **[docs/README.md](docs/README.md)**: Detailed documentation
- **[docs/deployment/](docs/deployment/)**: Deployment guides
- **[docs/development/](docs/development/)**: Development guides
- **[docs/infrastructure/](docs/infrastructure/)**: Infrastructure documentation

## Support

For issues:

1. Check the [FastAPI documentation](https://fastapi.tiangolo.com/)
2. Review application logs for specific error messages
3. Verify environment variables are correctly configured
4. Check the troubleshooting sections in the documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the coding standards
4. Add tests for new functionality
5. Update documentation as needed
6. Submit a pull request

## License

This project is provided as-is for educational and development purposes.

<!-- Trigger CD pipeline test: $(date) -->
