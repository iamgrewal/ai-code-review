# How to Use Speckit Commands with GitHub Copilot

Your speckit commands are now configured for GitHub Copilot! Here's how to use them:

## Quick Start

### 1. Creating a New Feature Specification
Type in GitHub Copilot chat:
```
@workspace /specify Add OAuth2 authentication to the code review system
```

**What happens:**
- Creates a new feature branch (e.g., `001-oauth2-auth`)
- Generates `specs/001-oauth2-auth/spec.md` with structured requirements
- Switches to the feature branch

### 2. Creating Implementation Plan
After creating a spec, type:
```
@workspace /plan I'm building this with FastAPI, SQLAlchemy, and JWT tokens
```

**What happens:**
- Creates `specs/001-oauth2-auth/plan.md` with technical implementation details
- Generates data models, API contracts, and architecture decisions
- Updates `.github/copilot-instructions.md` with new context

### 3. Breaking Down Into Tasks
```
@workspace /tasks Break the OAuth2 feature into development tasks
```

**What happens:**
- Creates `specs/001-oauth2-auth/tasks.md` with actionable development tasks
- Includes effort estimates and dependencies
- Ready for GitHub Issues or project tracking

### 4. Creating Domain Checklists
```
@workspace /checklist Create security checklist for authentication system
```

**What happens:**
- Generates comprehensive security checklist
- Includes testing, code review, and deployment considerations

## Command Examples for This Project

### For Code Review Enhancements
```
@workspace /specify Add code quality scoring to AI reviews
@workspace /plan Using Python machine learning libraries and the existing Copilot integration
@workspace /tasks 
```

### For API Improvements  
```
@workspace /specify Add webhook rate limiting and retry logic
@workspace /plan Using Redis for rate limiting and exponential backoff
@workspace /checklist Create reliability checklist for webhook processing
```

### For New AI Providers
```
@workspace /specify Add support for Claude AI as alternative to Copilot
@workspace /plan Following the existing AI abstract class pattern
@workspace /tasks Break into provider integration tasks
```

## File Structure After Commands

After running commands, you'll see:
```
specs/
├── 001-feature-name/
│   ├── spec.md           # Requirements and user stories
│   ├── plan.md          # Technical implementation plan  
│   ├── tasks.md         # Development task breakdown
│   └── contracts/       # API schemas and interfaces
├── 002-another-feature/
│   └── ...
```

## Integration with Existing Workflow

These specifications integrate with your existing development:

1. **Use specs for GitHub Issues** - Convert tasks.md items into GitHub Issues
2. **Reference in PRs** - Link PRs back to specification files  
3. **Update during development** - Keep specs current as implementation evolves
4. **Guide AI reviews** - Specifications help AI understand intended changes

## Troubleshooting

### "Commands not working"
If Copilot doesn't recognize the commands, try:
```
@workspace Please help me create a feature specification using the speckit system
```
Then explain what you want to build.

### "Script errors"
If you see script errors:
1. Ensure you're in the project root directory
2. Check that `.specify/` directory exists with all scripts
3. Verify scripts have execute permissions

### "Missing templates" 
If templates are missing:
```
ls .specify/templates/
```
Should show: `spec-template.md`, `plan-template.md`, `tasks-template.md`

## Manual Execution (Fallback)

If workspace commands don't work, you can run scripts directly:

```bash
# Create new feature
./.specify/scripts/bash/create-new-feature.sh --json "Add user authentication"

# Set up planning  
./.specify/scripts/bash/setup-plan.sh --json

# Update agent context
./.specify/scripts/bash/update-agent-context.sh copilot
```

The `--json` flag provides structured output that Copilot can parse.

## Next Steps

1. Try creating a simple feature spec: `@workspace /specify Add health check endpoint`
2. Generate an implementation plan for it
3. Break it into tasks
4. Implement using the guidance from the generated artifacts

Your speckit commands are now ready to use with GitHub Copilot!