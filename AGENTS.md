# Project Agents.md Guide for AI Agents

This Agents.md file provides comprehensive guidance for AI agents working with the Zergling FastAPI server template codebase.

## Project Structure for AI Agent Navigation

- `/src`: Source code that AI agents should analyze and modify
  - `/api.py`: Main FastAPI application with route handlers
  - `/config.py`: Configuration management and environment variables
  - `/database.py`: Database connection and session management
  - `/gcs_store.py`: Google Cloud Storage data store implementation
  - `/models.py`: Pydantic models for data validation
  - `/scheduler.py`: Background task scheduler
- `/tests`: Test files that AI agents should maintain and extend
  - `/test_api.py`: API endpoint tests
  - `/test_config.py`: Configuration tests
  - `/test_database.py`: Database tests
  - `/test_models.py`: Model validation tests
- `/infra`: Terraform infrastructure as code
  - `/main.tf`: Main infrastructure configuration
  - `/variables.tf`: Variable definitions
  - `/outputs.tf`: Output values
  - `/backend.tf`: Terraform state configuration
- `/scripts`: Utility scripts for deployment and testing
  - `/test_deployment.sh`: Manual deployment testing
  - `/test_api.sh`: API testing script
  - `/setup_zergling.sh`: Initial setup script
- `/docs`: Documentation files (organized by category)
  - `/README.md`: Documentation index and navigation guide
  - `/deployment/`: Deployment-related documentation
    - `/deploy.md`: Deployment instructions
    - `/deployment_errors.md`: Troubleshooting guide
  - `/development/`: Development guides
    - `/ci-cd.md`: CI/CD pipeline documentation
    - `/pipeline-setup.md`: Pipeline configuration guide
    - `/pre-commit-setup.md`: Pre-commit hooks setup
    - `/release-notes.md`: Release management guide
  - `/infrastructure/`: Infrastructure documentation
    - `/README.md`: Infrastructure overview
    - `/configuration_checklist.md`: Setup checklist
    - `/debug-log.md`: Infrastructure debugging
- `.github/workflows`: GitHub Actions workflows
  - `/pr-test.yml`: Pull request testing workflow
  - `/deploy.yml`: Deployment workflow

## Documentation Structure for AI Agents

This project uses a structured approach to documentation to ensure that both humans and AI agents can find the information they need. As an AI agent, refer to this structure to understand where to look for information and where to contribute new documentation.

-   **`README.md`**: The main entry point for human developers. It contains a high-level overview, setup instructions, and quick-start guides. *Agents should update this file only when making changes that affect the developer setup or user-facing features.*

-   **`AGENTS.md`** (This file): The primary guide for AI agents. It contains detailed instructions, coding conventions, testing requirements, and security guidelines that agents must follow. *Agents should refer to this file as their main source of truth for how to operate within the repository.*

-   **`docs/`**: This directory contains all detailed, long-form documentation organized by category:
    -   **`docs/README.md`**: Documentation index and navigation guide. *Agents should update this when adding new documentation.*
    -   **`docs/deployment/`**: Deployment and operational documentation
        -   **`docs/deployment/deploy.md`**: Step-by-step deployment instructions. *Agents can reference this to understand deployment processes.*
        -   **`docs/deployment/deployment_errors.md`**: Common deployment issues and troubleshooting. *Agents should consult this when debugging deployment problems.*
    -   **`docs/development/`**: Development workflow documentation
        -   **`docs/development/ci-cd.md`**: Detailed explanation of the CI/CD pipeline's architecture and workflows. *Agents should use this to understand how code gets from a pull request to production.*
        -   **`docs/development/pipeline-setup.md`**: Step-by-step guide for configuring the CI/CD pipeline, including setting up GitHub secrets and branch protection rules. *Agents can reference this to understand the deployment prerequisites.*
        -   **`docs/development/pre-commit-setup.md`**: Pre-commit hooks configuration and setup. *Agents should understand this for code quality enforcement.*
        -   **`docs/development/release-notes.md`**: Release management and versioning process. *Agents should follow this for release procedures.*
    -   **`docs/infrastructure/`**: Infrastructure and configuration documentation
        -   **`docs/infrastructure/README.md`**: In-depth documentation of the Terraform infrastructure, explaining each component's purpose and configuration. *Agents should consult this before making any changes to the `infra/` directory.*
        -   **`docs/infrastructure/configuration_checklist.md`**: Comprehensive setup checklist for new projects. *Agents should reference this when helping with project setup.*
        -   **`docs/infrastructure/debug-log.md`**: Infrastructure debugging and troubleshooting guide. *Agents can use this for operational tasks and problem resolution.*

## Coding Conventions for AI Agents

### General Conventions for Agents.md Implementation

- Use Python 3.11+ for all new code generated by AI agents
- AI agents should follow the existing code style in each file
- Agents.md requires meaningful variable and function names in AI agent output
- AI agents should add type hints for all functions and variables
- AI agents should add docstrings for all public functions and classes
- AI agents should use async/await patterns where appropriate
- AI agents should follow PEP 8 style guidelines

### FastAPI Guidelines for AI Agents

- AI agents should use FastAPI decorators for route definitions
- Keep route handlers generated by AI agents focused and single-purpose
- AI agents must use Pydantic models for request/response validation
- AI agents should implement proper error handling with HTTP status codes
- AI agents should add API documentation using FastAPI's automatic docs
- AI agents must use dependency injection for shared resources

### Testing Standards for AI Agents

- AI agents should write tests for all new functionality
- Use pytest for all test implementations
- AI agents should use async test functions when testing async code
- AI agents should mock external dependencies (GCS, databases, etc.)
- AI agents should achieve high test coverage (aim for 90%+)
- AI agents should use descriptive test names that explain the scenario

### Infrastructure Guidelines for AI Agents

- AI agents should not modify Terraform files without understanding the infrastructure
- AI agents should follow existing naming conventions in Terraform
- AI agents should ensure all Terraform resources have proper tags
- AI agents should maintain security best practices in infrastructure code
- AI agents should add proper documentation for new infrastructure components

## Testing Requirements for AI Agents

AI agents should run tests with the following commands:

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_api.py

# Run tests with verbose output
pytest -v

# Run tests and generate coverage report
pytest --cov=src --cov-report=html
```

## Pull Request Guidelines for AI Agents

When AI agents help create a PR, please ensure it:

1. Includes a clear description of the changes as guided by Agents.md
2. References any related issues that AI agents are addressing
3. Ensures all tests pass for code generated by AI agents
4. Includes API documentation updates for new endpoints
5. Updates relevant documentation files
6. Keeps PRs focused on a single concern as specified in Agents.md
7. Follows conventional commit message format

## Programmatic Checks for AI Agents

Before submitting changes generated by AI agents, run:

```bash
# Type checking
mypy src/

# Linting
flake8 src/

# Formatting check
black --check src/

# Run all tests
pytest

# Build Docker image locally
docker build -t zergling-test .
```

All checks must pass before AI agent generated code can be merged. Agents.md helps ensure AI agents follow these requirements.

## API Development Guidelines for AI Agents

### Adding New Endpoints

1. **Define Pydantic models** in `src/models.py` for request/response validation
2. **Add route handlers** in `src/api.py` with proper decorators
3. **Write comprehensive tests** in `tests/test_api.py`
4. **Update API documentation** with proper descriptions
5. **Add authentication** using the existing API key middleware
6. **Implement error handling** with appropriate HTTP status codes

### Data Storage Guidelines

- AI agents should use the existing GCS store interface in `src/gcs_store.py`
- AI agents should implement proper error handling for storage operations
- AI agents should use JSON serialization for data persistence
- AI agents should follow the existing data structure patterns

### Background Tasks

- AI agents should use the existing scheduler in `src/scheduler.py`
- AI agents should implement proper error handling for background tasks
- AI agents should add logging for task execution
- AI agents should ensure tasks are idempotent and safe to retry

## Security Guidelines for AI Agents

- AI agents must never hardcode secrets or sensitive information
- AI agents should use environment variables for configuration
- AI agents should validate all input data using Pydantic models
- AI agents should implement proper authentication for all endpoints
- AI agents should follow the principle of least privilege
- AI agents should add proper logging for security events

## Deployment Guidelines for AI Agents

- AI agents should not modify deployment configurations without understanding the pipeline
- AI agents should ensure new dependencies are added to `requirements.txt`
- AI agents should test Docker builds locally before deployment
- AI agents should verify that new environment variables are properly configured
- AI agents should ensure health checks pass for new functionality

## Error Handling Standards for AI Agents

- AI agents should use FastAPI's HTTPException for API errors
- AI agents should implement proper logging for all errors
- AI agents should provide meaningful error messages to users
- AI agents should handle edge cases gracefully
- AI agents should implement retry logic for transient failures

## Documentation Requirements for AI Agents

- AI agents should update README.md for user-facing changes
- AI agents should update relevant documentation in `/docs/`
- AI agents should add inline comments for complex logic
- AI agents should document API changes in code comments
- AI agents should maintain up-to-date type hints

## Performance Guidelines for AI Agents

- AI agents should use async operations where appropriate
- AI agents should implement proper connection pooling
- AI agents should use efficient data structures and algorithms
- AI agents should minimize database queries and external API calls
- AI agents should implement caching where beneficial
- AI agents should profile code for performance bottlenecks

## Monitoring and Observability

- AI agents should add structured logging for all operations
- AI agents should implement proper metrics and health checks
- AI agents should add error tracking and alerting
- AI agents should ensure logs are searchable and actionable
- AI agents should implement proper request tracing

## Code Review Checklist for AI Agents

Before submitting code, AI agents should verify:

- [ ] All tests pass
- [ ] Type checking passes
- [ ] Linting passes
- [ ] Code is properly formatted
- [ ] Documentation is updated
- [ ] Security considerations are addressed
- [ ] Performance implications are considered
- [ ] Error handling is implemented
- [ ] Logging is appropriate
- [ ] API documentation is accurate

## Configuration Checklist for New Projects

Whenever this repository is adapted for a new project or environment, you **must** consult the detailed checklist at `infra/configuration_checklist.md`.

- This checklist covers every Terraform variable, script variable, and configuration value that needs to be changed for a new deployment.
- It also documents common mistakes and pitfalls encountered during project migration.
- Before running `terraform apply` or deploying, ensure you have completed every item in the checklist.

**Agents and human developers:**
- Reference this checklist to avoid missed configuration steps, authentication issues, or deployment failures.
- Update the checklist if new variables or configuration requirements are added to the codebase.

## Automatic Release Management for AI Agents

AI agents must manage semantic versioning and release notes automatically as part of their workflow. The following rules apply:

- **Versioning:**
  - Agents must increment the project version in `pyproject.toml` (and any other version files) according to [Semantic Versioning](https://semver.org/):
    - **MAJOR** version when making incompatible API or infrastructure changes
    - **MINOR** version when adding functionality in a backwards-compatible manner
    - **PATCH** version when making backwards-compatible bug fixes or documentation-only changes
  - The version bump must be determined by the type of change requested by the user (e.g., "add feature" → MINOR, "fix bug" → PATCH, "breaking change" → MAJOR).

- **Release Notes:**
  - For every version bump, agents must append a new entry to `docs/release-notes.md` summarizing the changes, grouped by type (Added, Changed, Fixed, Removed, Security, Infra, Docs, etc.).
  - Release notes must be clear, human-readable, and reference the user request that triggered the change.

- **Changelog:**
  - Agents must continue to update `CHANGELOG.md` as before, but `docs/release-notes.md` is the canonical, user-facing release history.

- **Automation:**
  - All of the above must be performed automatically by the agent as part of any code or infrastructure change, without requiring manual intervention.

- **Documentation:**
  - Reference and link to `docs/release-notes.md` in `README.md` and other relevant documentation.

See `docs/release-notes.md` for the full release history. 