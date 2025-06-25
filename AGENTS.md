# Project Agents.md Guide for AI Agents

This Agents.md file provides comprehensive guidance for AI agents working with the Archon Content Server codebase.

## Request Management Workflow

### Initial Request Processing

When a user submits a request, AI agents must follow this structured approach:

1. **Request Analysis**: 
   - If the user has filled out `init_questionnaire.md`, analyze their requirements
   - If not, guide them to complete the questionnaire first
   - Create a new request document using the template from `docs/request-archive/request_template.md`
   - Save it as `current_request.md` in the root directory

2. **Jobs to be Done Analysis**:
   - Transform the user's request into a detailed "Jobs to be Done" analysis
   - Break down the request into specific, actionable tasks
   - Document all assumptions made during analysis
   - Create a step-by-step implementation plan

3. **TDD Approach**:
   - **ALWAYS** write tests first before implementing any functionality
   - Follow the Red-Green-Refactor cycle:
     - Write failing tests (Red)
     - Implement minimal code to pass tests (Green)
     - Refactor and improve code (Refactor)
   - Ensure all tests pass before proceeding to the next step

4. **Documentation-Based Development**:
   - Document every decision, assumption, and implementation step
   - Update the `current_request.md` file with progress notes
   - Include technical rationale for architectural decisions
   - Document any deviations from the original plan

### Implementation Process

For each implementation step:

1. **Planning Phase**:
   - Document the specific task to be completed
   - List all files that will be modified or created
   - Define acceptance criteria and test cases
   - Update `current_request.md` with the plan

2. **Development Phase**:
   - Write comprehensive tests first (TDD)
   - Implement the minimal code needed to pass tests
   - Follow existing code patterns and conventions
   - Ensure all linting and type checking passes

3. **Testing Phase**:
   - Run all existing tests to ensure no regressions
   - Run new tests to verify functionality
   - Perform manual testing if required
   - Document test results in `current_request.md`

4. **Documentation Phase**:
   - Update relevant documentation files
   - Add API documentation for new endpoints
   - Update README files if needed
   - Document any configuration changes

### Request Completion

When a request is completed:

1. **Final Testing**:
   - Run the complete test suite
   - Verify all acceptance criteria are met
   - Perform integration testing
   - Document final test results

2. **Documentation Finalization**:
   - Complete all implementation notes in `current_request.md`
   - Document lessons learned and best practices
   - Note any future improvements or follow-up tasks

3. **Archive Process**:
   - Move `current_request.md` to `docs/request-archive/` with a timestamp
   - Copy `docs/request-archive/request_template.md` to `current_request.md` in root
   - Update the archive index if needed

### Quality Assurance Requirements

AI agents must ensure:

- **Test Coverage**: All new code has comprehensive test coverage (90%+)
- **Documentation**: All changes are properly documented
- **Code Quality**: All code follows existing patterns and passes linting
- **Security**: All security best practices are followed
- **Performance**: Code meets performance requirements
- **Maintainability**: Code is clean, readable, and maintainable

### Communication Guidelines

- **Progress Updates**: Regularly update `current_request.md` with progress
- **Issue Documentation**: Document any problems encountered and their solutions
- **Decision Rationale**: Explain the reasoning behind technical decisions
- **Assumption Tracking**: Keep a running list of all assumptions made

## Project Structure for AI Agent Navigation

- `/src`: Source code that AI agents should analyze and modify
  - `/api.py`: Main FastAPI application with route handlers
  - `/config.py`: Configuration management and environment variables
  - `/database.py`: Data store interface definitions
  - `/in_memory_store.py`: In-memory store implementation used by default
  - `/models.py`: Pydantic models for data validation
  - `/scheduler.py`: Background task scheduler
- `/tests`: Test files that AI agents should maintain and extend
  - `/test_api.py`: API endpoint tests
  - `/test_config.py`: Configuration tests
  - `/test_models.py`: Model validation tests
- `/infra`: Terraform infrastructure as code
  - `/main.tf`: Main infrastructure configuration
  - `/variables.tf`: Variable definitions
  - `/outputs.tf`: Output values
  - `/backend.tf`: Terraform state configuration
- `/scripts`: Utility scripts for deployment and testing
  - `/test_deployment.sh`: Manual deployment testing
  - `/test_api.sh`: API testing script
  - `/setup_local_dev.sh`: Initial setup script
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
docker build -t archon-test .
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

Archon Content Server uses a simple in-memory store (`src/in_memory_store.py`).  There is **no external cloud storage** by default.  If persistent storage is required in the future, add a new `DataStore` implementation and corresponding tests.

Guidelines:

1. Re-use the `DataStore` interface in `src/database.py` for any new back-end.
2. Always write unit tests for the new store before implementation (TDD).
3. Use clear error handling (`ValueError`, `FileNotFoundError`, etc.) and propagate exceptions via the API layer.
4. Keep the in-memory store as the default fallback for local development and CI.

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

## Documentation Standards for AI Agents

### When to Write Documentation

AI agents **must** write or update documentation in the following scenarios:

1. **New Features**: When adding new functionality, endpoints, or capabilities
2. **Configuration Changes**: When modifying environment variables, settings, or infrastructure
3. **API Changes**: When adding, modifying, or removing API endpoints
4. **Infrastructure Updates**: When changing Terraform configurations or deployment processes
5. **Workflow Changes**: When modifying CI/CD pipelines, testing procedures, or development processes
6. **Bug Fixes**: When fixing issues that required significant investigation or have workarounds
7. **Security Updates**: When implementing security measures or addressing vulnerabilities
8. **Performance Improvements**: When making optimizations that change behavior or requirements
9. **Breaking Changes**: When making changes that require user action or migration
10. **User-Facing Changes**: When modifying anything that affects how users interact with the system

### Standard Documentation Format for LLMs

All documentation must follow this standardized format for optimal LLM comprehension and human readability:

```markdown
# Document Title

Brief one-sentence description of what this document covers.

## Overview

2-3 sentences explaining the purpose, scope, and context of this document. Include why someone would read this and what they'll learn.

## Prerequisites

- **Required**: List of prerequisites that must be completed before proceeding
- **Optional**: List of helpful but not required prerequisites
- **Tools**: Required software, CLI tools, or access levels needed

## Quick Start

Step-by-step instructions for the most common use case:

1. **Step 1**: Clear, actionable instruction
   ```bash
   # Example command or code
   ```
   *Expected output or result*

2. **Step 2**: Next instruction
   ```bash
   # Example command or code
   ```
   *Expected output or result*

3. **Step 3**: Continue as needed...

## Detailed Instructions

### Section 1: Configuration

Detailed explanation of configuration options:

| Setting | Description | Default | Required |
|---------|-------------|---------|----------|
| `SETTING_NAME` | What this setting controls | `default_value` | Yes/No |

**Example Configuration:**
```yaml
# Example configuration file
setting_name: value
```

### Section 2: Step-by-Step Process

Detailed breakdown of each step:

#### Step 1: Preparation
- What to do
- Why it's needed
- How to verify it worked

#### Step 2: Implementation
- Specific commands or code
- Expected outcomes
- Common issues and solutions

#### Step 3: Verification
- How to test the implementation
- What success looks like
- Troubleshooting tips

## Common Issues and Solutions

### Issue 1: [Descriptive Issue Name]

**Symptoms:**
- Error message or unexpected behavior
- When this issue occurs

**Cause:**
Brief explanation of why this happens

**Solution:**
```bash
# Commands to fix the issue
```

**Prevention:**
How to avoid this issue in the future

### Issue 2: [Another Issue]

[Follow same format as above]

## Troubleshooting

### Diagnostic Commands

```bash
# Command to check status
command_to_run

# Command to verify configuration
another_command
```

### Log Locations

- **Application logs**: `/path/to/logs`
- **System logs**: `/var/log/service`
- **Error logs**: `/path/to/errors`

### Debug Mode

How to enable debug logging and what to look for:

```bash
# Enable debug mode
export DEBUG=true
```

## Best Practices

- **Practice 1**: Explanation and rationale
- **Practice 2**: Explanation and rationale
- **Practice 3**: Explanation and rationale

## Security Considerations

- **Security Point 1**: What to be aware of
- **Security Point 2**: Best practices for security
- **Security Point 3**: Potential risks and mitigations

## Performance Notes

- **Performance Consideration 1**: Impact and optimization tips
- **Performance Consideration 2**: Monitoring recommendations
- **Performance Consideration 3**: Scaling considerations

## Related Documentation

- **[Related Doc 1](link)**: Brief description
- **[Related Doc 2](link)**: Brief description
- **[External Resource](link)**: External reference if applicable

## Changelog

- **Version 1.2.0**: Added new feature X
- **Version 1.1.0**: Fixed issue Y
- **Version 1.0.0**: Initial documentation
```

### Documentation Categories and Placement

AI agents must place documentation in the appropriate category:

#### `docs/deployment/`
- Deployment guides and procedures
- Production environment setup
- Troubleshooting deployment issues
- Operational procedures

#### `docs/development/`
- Development environment setup
- Code quality and testing procedures
- CI/CD pipeline documentation
- Release management processes

#### `docs/infrastructure/`
- Infrastructure configuration
- Terraform and cloud resource management
- Environment setup checklists
- Infrastructure troubleshooting

### Documentation Quality Standards

1. **Clarity**: Use simple, direct language. Avoid jargon unless necessary
2. **Completeness**: Include all necessary steps, commands, and expected outcomes
3. **Accuracy**: Test all commands and procedures before documenting
4. **Consistency**: Use consistent formatting, terminology, and structure
5. **Actionability**: Every instruction should be immediately actionable
6. **Verification**: Include ways to verify that steps were completed successfully
7. **Troubleshooting**: Anticipate common issues and provide solutions
8. **Context**: Explain why steps are necessary, not just what to do

### Documentation Maintenance

AI agents must:

- **Update existing docs** when making changes that affect documented procedures
- **Cross-reference** related documentation to maintain consistency
- **Version documentation** when making significant changes
- **Remove outdated information** when procedures change
- **Add examples** for complex procedures
- **Include error messages** and their solutions

### Documentation Review Checklist

Before finalizing any documentation, AI agents must verify:

- [ ] All commands and code examples are tested and working
- [ ] Prerequisites are clearly listed and accurate
- [ ] Step-by-step instructions are complete and in logical order
- [ ] Expected outcomes are clearly stated
- [ ] Common issues and solutions are included
- [ ] Security considerations are addressed
- [ ] Related documentation is linked
- [ ] Formatting is consistent with the standard template
- [ ] Language is clear and accessible to the target audience 