# Pre-commit Setup Guide

This guide explains how to set up and use pre-commit hooks for the Zergling FastAPI server template.

## What are Pre-commit Hooks?

Pre-commit hooks are automated scripts that run before every Git commit. They help ensure code quality by:
- **Formatting code** consistently (Black)
- **Catching linting errors** early (flake8)
- **Preventing bad commits** from entering the repository

## Quick Setup

### 1. Install Pre-commit

```bash
# Install pre-commit
pip install pre-commit

# Install the hooks in your repository
pre-commit install
```

That's it! The hooks are now active and will run automatically on every commit.

## Configuration

The `.pre-commit-config.yaml` file configures our hooks:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.10.0
    hooks:
      - id: black
        language_version: python3
        args: [src/, tests/]
  
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        additional_dependencies: []
        args: [src/, tests/]
```

### Hook Details

| Hook | Purpose | Version |
|------|---------|---------|
| **Black** | Code formatting | 24.10.0 |
| **flake8** | Linting | 7.0.0 |

## Usage

### Automatic (Recommended)

Every time you run `git commit`, the hooks run automatically:

```bash
git add .
git commit -m "feat: add new feature"
# Pre-commit hooks run here automatically
```

### Manual

Run hooks manually on all files:

```bash
pre-commit run --all-files
```

Run a specific hook:

```bash
pre-commit run black
pre-commit run flake8
```

### Skip Hooks (Not Recommended)

If you need to bypass hooks temporarily:

```bash
git commit --no-verify -m "emergency fix"
```

## What Happens When Hooks Run

### Success Case

```bash
$ git commit -m "feat: add new feature"
black....................................................................Passed
flake8...................................................................Passed
[feature/new-feature abc1234] feat: add new feature
```

### Failure Case

If hooks find issues, they will:
1. **Fix what they can** (Black)
2. **Report what they can't fix** (flake8)
3. **Stop the commit**

```bash
$ git commit -m "feat: add new feature"
black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted src/api.py
reformatted tests/test_api.py

flake8...................................................................Passed
```

**To fix this:**
1. The hooks have already fixed the files
2. Add the fixed files: `git add .`
3. Try committing again: `git commit -m "feat: add new feature"`

## Troubleshooting

### Common Issues

#### 1. Hook Installation Fails

```bash
# Reinstall hooks
pre-commit uninstall
pre-commit install
```

#### 2. Hooks Keep Modifying Files

This usually means your local tools are different from the pre-commit versions:

```bash
# Update pre-commit config
pre-commit autoupdate

# Or manually fix formatting
black src/ tests/
git add .
git commit -m "fix: apply formatting"
```

#### 3. Flake8 Errors

Check the `.flake8` configuration file and fix the reported issues:

```bash
# See all flake8 issues
flake8 src/ tests/

# Fix the issues manually, then commit
```

### Updating Hooks

To update to newer versions:

```bash
# Update all hooks
pre-commit autoupdate

# Or update specific hooks in .pre-commit-config.yaml
# Then run
pre-commit install
```

## Team Setup

### For New Team Members

1. **Clone the repository**
2. **Install pre-commit**:
   ```bash
   pip install pre-commit
   pre-commit install
   ```
3. **That's it!** Hooks will run automatically

### For Existing Projects

If you're adding pre-commit to an existing project:

1. **Install pre-commit** (see above)
2. **Fix existing issues**:
   ```bash
   pre-commit run --all-files
   # Fix any issues found
   git add .
   git commit -m "chore: apply pre-commit formatting"
   ```

## Integration with CI/CD

The same pre-commit hooks run in our CI pipeline:

- **Local**: `pre-commit run --all-files`
- **CI**: Same command in GitHub Actions

This ensures consistency between local development and CI.

## Best Practices

1. **Always use pre-commit hooks** - don't skip them
2. **Fix issues immediately** when hooks fail
3. **Keep hooks updated** with `pre-commit autoupdate`
4. **Use consistent formatting** across the team
5. **Document any custom configurations**

## Configuration Files

- `.pre-commit-config.yaml` - Hook configuration
- `.flake8` - Flake8 linting rules
- `pyproject.toml` - Project configuration (if needed)

## Need Help?

- **Pre-commit docs**: https://pre-commit.com/
- **Black docs**: https://black.readthedocs.io/
- **Flake8 docs**: https://flake8.pycqa.org/ 