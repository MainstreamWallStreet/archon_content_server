# Changelog

All notable changes to the Zergling FastAPI Server Template will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial FastAPI server template with GCP integration
- API key authentication
- GCS-based storage
- Background scheduler
- CI/CD pipeline with Cloud Build and direct Cloud Run deployment
- Comprehensive test suite
- Docker containerization
- Terraform infrastructure as code

### Changed
- Converted from legacy financial app to generic Zergling template
- Removed all business-specific logic and notifications
- Updated all service names and configurations
- Switched from Cloud Deploy to direct Cloud Run deployment for better reliability and simplicity
- Updated CI/CD pipeline to use GitHub Actions with Cloud Build and direct Cloud Run deployment
- Removed Cloud Deploy dependencies and configuration

### Removed
- Legacy earnings alerts
- Notification microservice integration
- Financial data processing
- Legacy business logic

### Fixed
- Resolved deployment issues by eliminating Cloud Deploy Skaffold version incompatibilities
- Improved deployment speed and reliability with direct Cloud Run deployment

## [0.1.0] - 2024-01-XX

### Added
- Initial FastAPI server template with GCP integration
- API key authentication for all endpoints
- GCS-based data storage with JSON persistence
- Background task scheduler
- Comprehensive test suite with async support
- CI/CD pipeline with Cloud Build and direct Cloud Run deployment
- Terraform infrastructure as code
- Docker containerization
- Health check endpoints
- Structured logging and error handling
- Development environment with hot reload
- Production-ready configuration

