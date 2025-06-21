# Documentation

Welcome to the Zergling FastAPI Server Template documentation. This guide will help you navigate through all available documentation and get started with the project.

## 📚 Quick Navigation

### 🚀 Getting Started
- **[Main README](../README.md)** - Project overview, features, and quick start guide
- **[Configuration Checklist](infrastructure/configuration_checklist.md)** - Complete setup checklist for new projects

### 🏗️ Infrastructure & Deployment
- **[Infrastructure Overview](infrastructure/README.md)** - GCP resources and Terraform configuration
- **[Deployment Guide](deployment/deploy.md)** - Step-by-step deployment instructions
- **[Troubleshooting](deployment/deployment_errors.md)** - Common deployment issues and solutions
- **[Debug Guide](infrastructure/debug-log.md)** - Infrastructure debugging and troubleshooting

### 🔧 Development
- **[CI/CD Pipeline](development/ci-cd.md)** - GitHub Actions workflow documentation
- **[Pipeline Setup](development/pipeline-setup.md)** - Detailed pipeline configuration guide
- **[Pre-commit Setup](development/pre-commit-setup.md)** - Code quality hooks configuration
- **[Release Management](development/release-notes.md)** - Version management and release process

## 📖 Documentation Structure

```
docs/
├── README.md                    # This file - Documentation index
├── deployment/                  # Deployment-related documentation
│   ├── deploy.md               # Deployment instructions
│   └── deployment_errors.md    # Troubleshooting guide
├── development/                 # Development guides
│   ├── ci-cd.md               # CI/CD pipeline documentation
│   ├── pipeline-setup.md      # Pipeline configuration
│   ├── pre-commit-setup.md    # Pre-commit hooks setup
│   └── release-notes.md       # Release management
└── infrastructure/             # Infrastructure documentation
    ├── README.md              # Infrastructure overview
    ├── configuration_checklist.md # Setup checklist
    └── debug-log.md           # Debugging guide
```

## 🎯 Common Tasks

### For New Projects
1. **[Configuration Checklist](infrastructure/configuration_checklist.md)** - Follow this comprehensive checklist
2. **[Main README](../README.md)** - Review project features and requirements
3. **[Deployment Guide](deployment/deploy.md)** - Deploy your infrastructure

### For Developers
1. **[CI/CD Pipeline](development/ci-cd.md)** - Understand the automated workflow
2. **[Pre-commit Setup](development/pre-commit-setup.md)** - Set up code quality tools
3. **[Release Management](development/release-notes.md)** - Learn version management

### For Troubleshooting
1. **[Troubleshooting Guide](deployment/deployment_errors.md)** - Common deployment issues
2. **[Debug Guide](infrastructure/debug-log.md)** - Infrastructure debugging
3. **[Infrastructure Overview](infrastructure/README.md)** - Understand the architecture

## 🔗 External Resources

- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - FastAPI framework docs
- **[Google Cloud Documentation](https://cloud.google.com/docs)** - GCP services and APIs
- **[Terraform Documentation](https://www.terraform.io/docs)** - Infrastructure as Code
- **[GitHub Actions Documentation](https://docs.github.com/en/actions)** - CI/CD workflows

## 📝 Contributing to Documentation

When adding new documentation:

1. **Choose the right directory**:
   - `deployment/` - For deployment and operational guides
   - `development/` - For development workflows and tools
   - `infrastructure/` - For infrastructure and configuration

2. **Update this index** - Add your new document to the appropriate section above

3. **Follow naming conventions**:
   - Use kebab-case for filenames
   - Use descriptive names that indicate the content
   - Include `.md` extension

4. **Link from main README** - Update the main README.md if your document should be prominently featured

## 🆘 Getting Help

If you can't find what you're looking for:

1. Check the **[troubleshooting guides](deployment/deployment_errors.md)**
2. Review the **[configuration checklist](infrastructure/configuration_checklist.md)** for setup issues
3. Look at the **[debug guide](infrastructure/debug-log.md)** for infrastructure problems
4. Check the **[main README](../README.md)** for quick start information

For additional help, please refer to the project's issue tracker or documentation. 