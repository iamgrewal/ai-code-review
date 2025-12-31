# Speckit Commands for GitHub Copilot

This file provides GitHub Copilot with access to the speckit command system. Use these patterns when working with feature specifications.

## Available Commands

### @workspace /specify [feature description]
Creates or updates a feature specification from natural language description.

**Usage:** `@workspace /specify Add user authentication with OAuth2`

**What it does:**
1. Generates a concise branch name (2-4 words)
2. Checks for existing branches to avoid conflicts
3. Creates new feature branch and specification
4. Sets up the specification structure

**Implementation:**
- Analyzes feature description for key concepts
- Uses action-noun format for naming (e.g., "add-user-auth")
- Runs `.specify/scripts/bash/create-new-feature.sh` script
- Creates spec file from template

### @workspace /plan [additional context]
Creates technical implementation plan from existing specification.

**Usage:** `@workspace /plan I am building with FastAPI and PostgreSQL`

**What it does:**
1. Loads existing feature specification
2. Creates technical implementation plan
3. Generates design artifacts (data models, contracts)
4. Updates agent context files

**Implementation:**
- Runs `.specify/scripts/bash/setup-plan.sh` script
- Follows structured planning workflow
- Creates research.md, data-model.md, contracts/
- Updates .github/copilot-instructions.md with new context

### @workspace /tasks [context]
Breaks implementation plan into actionable tasks.

**Usage:** `@workspace /tasks Break down the authentication feature`

**What it does:**
1. Reads current implementation plan
2. Creates numbered, actionable tasks
3. Estimates effort and dependencies
4. Generates task tracking format

### @workspace /checklist [domain]
Creates domain-specific implementation checklist.

**Usage:** `@workspace /checklist Create security checklist for authentication`

**What it does:**
1. Generates comprehensive checklist for domain
2. Includes testing, security, documentation items
3. Creates trackable completion format

## Script Integration

All commands integrate with the existing `.specify/scripts/bash/` system:

- `create-new-feature.sh` - Creates feature branch and spec
- `setup-plan.sh` - Initializes planning workflow  
- `update-agent-context.sh` - Updates agent-specific context

## File Structure

```
.specify/
├── scripts/bash/           # Command implementation scripts
├── templates/              # Specification templates
└── memory/                 # Constitution and constraints

specs/
├── [number]-[name]/        # Feature specifications
│   ├── spec.md            # Feature requirements
│   ├── plan.md            # Implementation plan
│   ├── research.md        # Research findings
│   └── contracts/         # API contracts
```

## Usage Patterns

1. **New Feature Workflow:**
   ```
   @workspace /specify Add user dashboard with analytics
   @workspace /plan Using React and Node.js
   @workspace /tasks
   ```

2. **Planning Existing Feature:**
   ```
   @workspace /plan Review current spec and create implementation plan
   @workspace /checklist Create testing checklist
   ```

3. **Breaking Down Work:**
   ```
   @workspace /tasks Break authentication into development tasks
   @workspace /checklist Security review for auth system
   ```

## Command Execution

When executing these commands, GitHub Copilot should:

1. **Parse the command and arguments**
2. **Run the appropriate script** with proper escaping
3. **Parse JSON output** from scripts for file paths
4. **Load and process** the generated/updated files
5. **Provide summary** of what was created/updated

## Error Handling

- **Empty feature description:** Error with guidance
- **Script execution failure:** Show script output and suggest fixes
- **Missing dependencies:** Guide user to run setup scripts
- **Branch conflicts:** Suggest alternative names or cleanup

## Integration Notes

- All scripts are designed to work with bash
- JSON output provides file paths for further processing  
- Agent context updates ensure Copilot stays informed
- Templates ensure consistent specification format