# GitHub Copilot Workspace Commands

This document defines custom commands and workflows for GitHub Copilot in this workspace.

## Command System Integration

### Custom @workspace Commands

When users type commands starting with `@workspace /`, interpret and execute them using the speckit system:

#### `/specify [feature_description]`
**Purpose:** Create feature specification from natural language
**Example:** `@workspace /specify Add user authentication with OAuth2`
**Action:** 
1. Extract feature description from arguments
2. Generate concise branch name (action-noun format)
3. Run: `.specify/scripts/bash/create-new-feature.sh --json "$ARGUMENTS"`
4. Parse JSON output for BRANCH_NAME and SPEC_FILE
5. Load and present the created specification

#### `/plan [context]` 
**Purpose:** Create technical implementation plan
**Example:** `@workspace /plan Using FastAPI and PostgreSQL`
**Action:**
1. Run: `.specify/scripts/bash/setup-plan.sh --json`
2. Parse JSON for FEATURE_SPEC, IMPL_PLAN paths
3. Load specification template and fill with technical details
4. Update agent context via: `.specify/scripts/bash/update-agent-context.sh copilot`

#### `/tasks [context]`
**Purpose:** Break plan into actionable tasks
**Example:** `@workspace /tasks Break authentication into development tasks`
**Action:**
1. Read current implementation plan
2. Generate numbered, actionable tasks with effort estimates
3. Create dependency mapping
4. Format as trackable task list

#### `/checklist [domain]`
**Purpose:** Generate domain-specific implementation checklist
**Example:** `@workspace /checklist Security checklist for authentication`
**Action:**
1. Generate comprehensive domain checklist
2. Include testing, security, documentation requirements
3. Format as checkable items

## Workflow Integration

### Feature Development Process
1. **Specification:** `@workspace /specify [description]` → Creates spec in `specs/[N]-[name]/`
2. **Planning:** `@workspace /plan [tech context]` → Generates technical plan
3. **Tasking:** `@workspace /tasks` → Creates actionable task breakdown
4. **Implementation:** Use generated artifacts to guide development

### File Structure Awareness
```
specs/[number]-[feature-name]/
├── spec.md           # Feature requirements  
├── plan.md           # Technical implementation plan
├── research.md       # Research and decisions
├── tasks.md          # Actionable task list
└── contracts/        # API contracts and schemas
```

## Script Execution Guidelines

### Error Handling
- **Script failures:** Display output and suggest fixes
- **Missing arguments:** Prompt for required information
- **Branch conflicts:** Suggest alternative names

### JSON Parsing
All scripts output JSON with file paths:
```json
{
  "BRANCH_NAME": "feature-branch-name",
  "SPEC_FILE": "path/to/spec.md",
  "IMPL_PLAN": "path/to/plan.md"
}
```

### Context Updates
After planning operations, run:
```bash
.specify/scripts/bash/update-agent-context.sh copilot
```
This updates `.github/copilot-instructions.md` with new project context.

## Command Recognition Patterns

Recognize these user inputs as speckit commands:

- `/specify ...` or `specify ...` → Feature specification
- `/plan ...` or `plan ...` → Implementation planning  
- `/tasks` or `tasks` → Task breakdown
- `/checklist ...` or `checklist ...` → Domain checklist

When these patterns are detected, execute the appropriate workflow rather than treating as general questions.

## Integration with Existing Codebase

This command system complements the main Gitea AI Code Reviewer project:

- **Specifications** define new features for the code review system
- **Plans** detail how to implement webhook enhancements, AI improvements, etc.
- **Tasks** break down complex changes to the FastAPI service
- **Checklists** ensure security, testing for AI integrations

Use the existing project patterns (FastAPI, Docker, environment config) when generating technical plans and implementations.