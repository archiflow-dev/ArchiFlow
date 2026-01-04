# Phase 3 Frontend API Integration - Manual Test Guide

**Document Version:** 1.0
**Last Updated:** 2026-01-04
**Reference:** `docs/web/designs/web-app-v3.1-implementation-plan.md`
**Purpose:** Step-by-step manual testing guide for Phase 3 Frontend API Integration

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Test Environment Setup](#test-environment-setup)
3. [Test Plan Overview](#test-plan-overview)
4. [Health Check Tests](#1-health-check-tests)
5. [Agent API Tests](#2-agent-api-tests)
6. [Session API Tests](#3-session-api-tests)
7. [Workflow API Tests](#4-workflow-api-tests)
8. [Artifact API Tests](#5-artifact-api-tests)
9. [Message API Tests](#6-message-api-tests)
10. [Integration Test Scenarios](#7-integration-test-scenarios)
11. [Expected Results](#expected-results)
12. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

- **Python 3.10+** - For running the backend server
- **Node.js 18+** - For running frontend tests (optional for API testing)
- **curl** or **Postman** - For making API requests

### Required Python Packages

```bash
# Install dependencies
pip install -r requirements-web.txt

# Key packages:
# - fastapi>=0.109.0
# - uvicorn[standard]>=0.27.0
# - python-socketio>=5.10.0
# - pydantic>=2.5.0
# - sqlalchemy>=2.0.0
# - aiosqlite>=0.19.0
# - httpx>=0.25.0  # For testing
```

### Project Structure

```
archiflow/
├── src/web_backend/          # Backend source
│   ├── main.py              # FastAPI app entry point
│   ├── routes/              # API route handlers
│   ├── services/            # Business logic
│   └── models/              # Database models
├── frontend-prototype/       # Frontend source
│   └── src/services/        # API client implementation
└── tests/web_backend/        # Test files
    └── test_phase3_integration.py
```

---

## Test Environment Setup

### Step 1: Start the Backend Server

```bash
# From project root
cd C:\projects\dev\archiflow

# Start the server (with hot reload)
uvicorn src.web_backend.main:socket_app --reload --port 8000

# Or without reload
uvicorn src.web_backend.main:socket_app --port 8000
```

**Expected Output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxx] using StatReload
INFO:     Started server process [xxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 2: Verify Server is Running

```bash
curl http://localhost:8000/api/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "3.1.0",
  "app_name": "ArchiFlow Web API"
}
```

### Step 3: Access API Documentation

Open in browser:
- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc

---

## Test Plan Overview

| Test Category | Endpoints | Priority |
|--------------|-----------|----------|
| 1. Health Check | `/api/health` | Critical |
| 2. Agent API | `/api/agents/` | High |
| 3. Session API | `/api/sessions/` | Critical |
| 4. Workflow API | `/api/sessions/{id}/workflow/` | High |
| 5. Artifact API | `/api/sessions/{id}/artifacts/` | High |
| 6. Message API | `/api/sessions/{id}/messages/` | High |
| 7. Integration | End-to-end flows | High |

---

## 1. Health Check Tests

### Test 1.1: Basic Health Check

**Endpoint:** `GET /api/health`

**Request:**
```bash
curl -X GET http://localhost:8000/api/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "version": "3.1.0",
  "app_name": "ArchiFlow Web API"
}
```

**Verification:**
- [ ] Status is "healthy"
- [ ] Version is present
- [ ] App name is "ArchiFlow Web API"

---

## 2. Agent API Tests

### Test 2.1: List All Agents

**Endpoint:** `GET /api/agents/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/agents/
```

**Expected Response:**
```json
{
  "agents": [
    {
      "id": "comic",
      "name": "Comic Creator",
      "description": "Creates comic books from story prompts...",
      "category": "creative",
      "workflow_type": "phase_heavy",
      "capabilities": [...],
      "supports_streaming": true,
      "supports_artifacts": true,
      "supports_workflow": true
    },
    {
      "id": "ppt",
      "name": "Presentation Designer",
      ...
    },
    {
      "id": "coding",
      "name": "Coding Assistant",
      ...
    },
    {
      "id": "research",
      "name": "Research Assistant",
      ...
    }
  ],
  "total": 4,
  "categories": [...]
}
```

**Verification:**
- [ ] Returns 4 agents
- [ ] Each agent has: id, name, description, category, workflow_type
- [ ] Total count matches agents array length

### Test 2.2: Get Agent by Type

**Endpoint:** `GET /api/agents/{agent_type}`

**Request:**
```bash
curl -X GET http://localhost:8000/api/agents/coding
```

**Expected Response:**
```json
{
  "id": "coding",
  "name": "Coding Assistant",
  "description": "Helps write, review, and debug code...",
  "category": "development",
  "workflow_type": "chat_heavy",
  "capabilities": [
    {"name": "code_writing", "description": "..."},
    {"name": "code_review", "description": "..."},
    ...
  ]
}
```

**Verification:**
- [ ] Returns single agent with matching ID
- [ ] All fields populated

### Test 2.3: Search Agents

**Endpoint:** `GET /api/agents/?search={query}`

**Request:**
```bash
curl -X GET "http://localhost:8000/api/agents/?search=code"
```

**Expected Response:**
```json
{
  "agents": [
    {
      "id": "coding",
      "name": "Coding Assistant",
      ...
    }
  ],
  "total": 1
}
```

**Verification:**
- [ ] Returns filtered results matching search query

---

## 3. Session API Tests

### Test 3.1: Create Session

**Endpoint:** `POST /api/sessions/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{
    "agent_type": "coding",
    "user_prompt": "Build a REST API with FastAPI"
  }'
```

**Expected Response:**
```json
{
  "id": "session_xxxxx",
  "agent_type": "coding",
  "user_prompt": "Build a REST API with FastAPI",
  "status": "created",
  "user_id": "default_user",
  "created_at": "2026-01-04T...",
  "updated_at": "2026-01-04T..."
}
```

**Verification:**
- [ ] Session ID is generated
- [ ] Status is "created"
- [ ] Timestamps are present
- [ ] Workspace directory is created in `data/workspaces/`

**Save the session_id for subsequent tests:**
```bash
# Windows Command Prompt
set SESSION_ID=session_xxxxx

# PowerShell
$SESSION_ID="session_xxxxx"

# Linux/Mac
export SESSION_ID=session_xxxxx
```

### Test 3.2: List Sessions

**Endpoint:** `GET /api/sessions/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/
```

**Expected Response:**
```json
{
  "sessions": [...],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "has_more": false
}
```

**Verification:**
- [ ] Returns array of sessions
- [ ] Pagination metadata present

### Test 3.3: Get Session by ID

**Endpoint:** `GET /api/sessions/{session_id}`

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/%SESSION_ID%
```

**Expected Response:**
```json
{
  "id": "session_xxxxx",
  "agent_type": "coding",
  ...
}
```

**Verification:**
- [ ] Returns the created session details

### Test 3.4: Start Session

**Endpoint:** `POST /api/sessions/{session_id}/start`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/start
```

**Expected Response:**
```json
{
  "id": "session_xxxxx",
  "status": "running",
  ...
}
```

**Verification:**
- [ ] Status changes from "created" to "running"

### Test 3.5: Pause Session

**Endpoint:** `POST /api/sessions/{session_id}/pause`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/pause
```

**Expected Response:**
```json
{
  "id": "session_xxxxx",
  "status": "paused",
  ...
}
```

**Verification:**
- [ ] Status changes to "paused"

### Test 3.6: Resume Session

**Endpoint:** `POST /api/sessions/{session_id}/resume`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/resume
```

**Expected Response:**
```json
{
  "id": "session_xxxxx",
  "status": "running",
  ...
}
```

**Verification:**
- [ ] Status changes back to "running"

---

## 4. Workflow API Tests

### Test 4.1: Get Workflow State

**Endpoint:** `GET /api/sessions/{session_id}/workflow/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/%SESSION_ID%/workflow/
```

**Expected Response (for coding agent):**
```json
{
  "session_id": "session_xxxxx",
  "agent_type": "coding",
  "current_phase": null,
  "phases": [
    {
      "id": "planning",
      "name": "Planning",
      "description": "Analyze task and create implementation plan",
      "status": "pending",
      "order": 1,
      "requires_approval": true,
      "artifacts": []
    },
    {
      "id": "implementation",
      "name": "Implementation",
      "description": "Write and modify code",
      "status": "pending",
      "order": 2,
      "requires_approval": true,
      "artifacts": []
    },
    {
      "id": "verification",
      "name": "Verification",
      "description": "Run tests and verify changes",
      "status": "pending",
      "order": 3,
      "requires_approval": true,
      "artifacts": []
    }
  ],
  "progress_percent": 0.0
}
```

**Verification:**
- [ ] Returns workflow with phases
- [ ] Each phase has: id, name, description, status, order
- [ ] Progress percent calculated correctly

### Test 4.2: Start Workflow

**Endpoint:** `POST /api/sessions/{session_id}/workflow/start`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/workflow/start
```

**Expected Response:**
```json
{
  "session_id": "session_xxxxx",
  "status": "running",
  "current_phase": "planning",
  ...
}
```

**Verification:**
- [ ] Workflow status changes to "running"
- [ ] First phase starts

### Test 4.3: Set Phase to Awaiting Approval

**Endpoint:** `POST /api/sessions/{session_id}/workflow/phases/{phase_id}/awaiting-approval`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/workflow/phases/planning/awaiting-approval
```

**Expected Response:**
```json
{
  "phase_id": "planning",
  "status": "awaiting_approval",
  "message": "Phase set to awaiting approval"
}
```

**Verification:**
- [ ] Phase status changes to "awaiting_approval"

### Test 4.4: Approve Phase

**Endpoint:** `POST /api/sessions/{session_id}/workflow/phases/{phase_id}/approve`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/workflow/phases/planning/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "feedback": "Great plan! Proceed with implementation."
  }'
```

**Expected Response:**
```json
{
  "phase_id": "planning",
  "status": "approved",
  "message": "Phase approved successfully",
  "feedback_stored": true
}
```

**Verification:**
- [ ] Phase status changes to "approved"
- [ ] Feedback is stored
- [ ] Next phase may start automatically

### Test 4.5: Reject Phase

**Endpoint:** `POST /api/sessions/{session_id}/workflow/phases/{phase_id}/approve`

**Request (with approved: false):**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/workflow/phases/planning/approve \
  -H "Content-Type: application/json" \
  -d '{
    "approved": false,
    "feedback": "Need more details on the architecture."
  }'
```

**Expected Response:**
```json
{
  "phase_id": "planning",
  "status": "rejected",
  "message": "Phase rejected",
  "feedback_stored": true
}
```

**Verification:**
- [ ] Phase status changes to "rejected"
- [ ] Feedback is stored

---

## 5. Artifact API Tests

### Test 5.1: List Artifacts

**Endpoint:** `GET /api/sessions/{session_id}/artifacts/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/%SESSION_ID%/artifacts/
```

**Expected Response:**
```json
{
  "artifacts": [
    {
      "name": "artifacts",
      "path": "artifacts",
      "is_directory": true,
      "size": null,
      "modified_at": "2026-01-04T..."
    },
    {
      "name": "exports",
      "path": "exports",
      "is_directory": true,
      "size": null,
      "modified_at": "2026-01-04T..."
    }
  ],
  "path": "/",
  "total": 2
}
```

**Verification:**
- [ ] Returns workspace structure
- [ ] Default directories created

### Test 5.2: Create Artifact

**Endpoint:** `POST /api/sessions/{session_id}/artifacts/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/artifacts/ \
  -H "Content-Type: application/json" \
  -d '{
    "path": "test.md",
    "content": "# Test Artifact\n\nThis is a test file created via API."
  }'
```

**Expected Response:**
```json
{
  "name": "test.md",
  "path": "test.md",
  "is_directory": false,
  "size": 56,
  "mime_type": "text/markdown",
  "modified_at": "2026-01-04T..."
}
```

**Verification:**
- [ ] Artifact created successfully
- [ ] File size calculated
- [ ] MIME type detected

### Test 5.3: Get Artifact Content

**Endpoint:** `GET /api/sessions/{session_id}/artifacts/{artifact_path}`

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/%SESSION_ID%/artifacts/test.md
```

**Expected Response:**
```json
{
  "path": "test.md",
  "content": "# Test Artifact\n\nThis is a test file created via API.",
  "content_base64": null,
  "mime_type": "text/markdown",
  "size": 56,
  "is_binary": false
}
```

**Verification:**
- [ ] Content matches what was created
- [ ] is_binary is false for text files

### Test 5.4: Update Artifact

**Endpoint:** `PUT /api/sessions/{session_id}/artifacts/{artifact_path}`

**Request:**
```bash
curl -X PUT http://localhost:8000/api/sessions/%SESSION_ID%/artifacts/test.md \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# Updated Test Artifact\n\nThis file has been updated."
  }'
```

**Expected Response:**
```json
{
  "name": "test.md",
  "path": "test.md",
  "is_directory": false,
  "size": 63,
  ...
}
```

**Verification:**
- [ ] File size changed
- [ ] Content updated

### Test 5.5: Delete Artifact

**Endpoint:** `DELETE /api/sessions/{session_id}/artifacts/{artifact_path}`

**Request:**
```bash
curl -X DELETE http://localhost:8000/api/sessions/%SESSION_ID%/artifacts/test.md
```

**Expected Response:**
```
HTTP 204 No Content
```

**Verification:**
- [ ] Returns 204 status code
- [ ] File no longer appears in list

---

## 6. Message API Tests

### Test 6.1: List Messages

**Endpoint:** `GET /api/sessions/{session_id}/messages/`

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/%SESSION_ID%/messages/
```

**Expected Response:**
```json
{
  "messages": [],
  "total": 0,
  "session_id": "session_xxxxx"
}
```

**Verification:**
- [ ] Returns empty array initially

### Test 6.2: Send User Message

**Endpoint:** `POST /api/sessions/{session_id}/messages/`

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "Can you help me build a REST API?"
  }'
```

**Expected Response:**
```json
{
  "id": "msg_xxxxx",
  "session_id": "session_xxxxx",
  "role": "user",
  "content": "Can you help me build a REST API?",
  "sequence": 1,
  "tool_name": null,
  "tool_call_id": null,
  "created_at": "2026-01-04T..."
}
```

**Verification:**
- [ ] Message ID generated
- [ ] Sequence number incremented
- [ ] Role set correctly

### Test 6.3: Send Assistant Message

**Request:**
```bash
curl -X POST http://localhost:8000/api/sessions/%SESSION_ID%/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "role": "assistant",
    "content": "I'\''d be happy to help! Let'\''s start by..."
  }'
```

**Expected Response:**
```json
{
  "id": "msg_yyyyy",
  "role": "assistant",
  "sequence": 2,
  ...
}
```

**Verification:**
- [ ] Sequence number increments
- [ ] Different message ID

### Test 6.4: List Messages After Sending

**Request:**
```bash
curl -X GET http://localhost:8000/api/sessions/%SESSION_ID%/messages/
```

**Expected Response:**
```json
{
  "messages": [
    {
      "id": "msg_xxxxx",
      "role": "user",
      ...
    },
    {
      "id": "msg_yyyyy",
      "role": "assistant",
      ...
    }
  ],
  "total": 2,
  "session_id": "session_xxxxx"
}
```

**Verification:**
- [ ] All messages returned in order
- [ ] Total count matches

---

## 7. Integration Test Scenarios

### Scenario 7.1: Complete Session Lifecycle

**Steps:**

1. Create a session:
```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "coding", "user_prompt": "Build a todo app"}'
```

2. Start the session:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/start
```

3. Send a message:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/messages/ \
  -H "Content-Type: application/json" \
  -d '{"role": "user", "content": "Start with React"}'
```

4. Create an artifact:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/artifacts/ \
  -H "Content-Type: application/json" \
  -d '{"path": "TodoApp.tsx", "content": "..."}'
```

5. Pause the session:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/pause
```

**Verification:**
- [ ] All steps complete without errors
- [ ] Session state persists correctly

### Scenario 7.2: Workflow Approval Flow

**Steps:**

1. Create a session with phase_heavy agent (comic or ppt):
```bash
curl -X POST http://localhost:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "comic", "user_prompt": "Create a comic about AI"}'
```

2. Start workflow:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/workflow/start
```

3. Set phase to awaiting approval:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/workflow/phases/{phase_id}/awaiting-approval
```

4. Approve with feedback:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/workflow/phases/{phase_id}/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true, "feedback": "Looks good!"}'
```

**Verification:**
- [ ] Phase transitions work correctly
- [ ] Feedback is stored

### Scenario 7.3: Artifact Management

**Steps:**

1. Create nested directory structure:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/artifacts/ \
  -H "Content-Type: application/json" \
  -d '{"path": "src/components", "content": "", "is_directory": true}'
```

2. Create file in directory:
```bash
curl -X POST http://localhost:8000/api/sessions/{id}/artifacts/ \
  -H "Content-Type: application/json" \
  -d '{"path": "src/components/Button.tsx", "content": "..."}'
```

3. List directory contents:
```bash
curl -X GET http://localhost:8000/api/sessions/{id}/artifacts/src/components/
```

4. Update file:
```bash
curl -X PUT http://localhost:8000/api/sessions/{id}/artifacts/src/components/Button.tsx \
  -H "Content-Type: application/json" \
  -d '{"content": "updated content..."}'
```

**Verification:**
- [ ] Directories created correctly
- [ ] Files created in correct paths
- [ ] Updates work properly

---

## Expected Results

### Success Criteria

All tests should pass with the following criteria:

| Category | Expected Pass Rate |
|----------|-------------------|
| Health Check | 100% |
| Agent API | 100% |
| Session API | 100% |
| Workflow API | 100% |
| Artifact API | 100% |
| Message API | 100% |
| Integration | 100% |

### Response Time Expectations

| Endpoint Type | Expected Response Time |
|--------------|----------------------|
| Health Check | < 50ms |
| Agent List | < 100ms |
| Session Create | < 200ms |
| Session Get | < 100ms |
| Message Send | < 150ms |
| Artifact Create | < 200ms |

### Response Format Standards

All responses should include:
- Proper HTTP status codes
- JSON content type
- Consistent field naming (snake_case)
- Timestamps in ISO 8601 format

---

## Troubleshooting

### Common Issues

#### Issue: Server fails to start

**Symptoms:** Error on `uvicorn` command

**Solutions:**
1. Check if port 8000 is already in use:
```bash
# Windows
netstat -ano | findstr :8000

# Kill the process if needed
taskkill /PID {pid} /F
```

2. Verify dependencies installed:
```bash
pip list | findstr fastapi
pip install -r requirements-web.txt
```

#### Issue: 404 Not Found on endpoints

**Symptoms:** API endpoints return 404

**Solutions:**
1. Check API prefix in config
2. Verify URL includes `/api` prefix
3. Check route registration in `main.py`

#### Issue: 500 Internal Server Error

**Symptoms:** Endpoints return 500 with error details

**Solutions:**
1. Check server logs for detailed error
2. Verify database is initialized
3. Check workspace directory permissions

#### Issue: Phase approval returns AttributeError

**Symptoms:**
```json
{"detail": "Internal server error", "type": "AttributeError"}
```

**Solutions:**
1. Check workflow controller implementation
2. Verify workflow state is properly initialized
3. Check phase ID exists in workflow definition

### Debug Mode

Enable debug logging:

```bash
# Set environment variable
set DEBUG=true

# Or pass directly
uvicorn src.web_backend.main:socket_app --reload --log-level debug
```

### Test Data Cleanup

Remove test sessions:

```bash
# Delete specific session
curl -X DELETE http://localhost:8000/api/sessions/{session_id}

# Clean workspace directories
rm -rf data/workspaces/default_user/session_*
```

---

## Test Checklist

Use this checklist to track test completion:

### Health Check
- [ ] Test 1.1: Basic health check

### Agent API
- [ ] Test 2.1: List all agents
- [ ] Test 2.2: Get agent by type
- [ ] Test 2.3: Search agents

### Session API
- [ ] Test 3.1: Create session
- [ ] Test 3.2: List sessions
- [ ] Test 3.3: Get session by ID
- [ ] Test 3.4: Start session
- [ ] Test 3.5: Pause session
- [ ] Test 3.6: Resume session

### Workflow API
- [ ] Test 4.1: Get workflow state
- [ ] Test 4.2: Start workflow
- [ ] Test 4.3: Set phase to awaiting approval
- [ ] Test 4.4: Approve phase
- [ ] Test 4.5: Reject phase

### Artifact API
- [ ] Test 5.1: List artifacts
- [ ] Test 5.2: Create artifact
- [ ] Test 5.3: Get artifact content
- [ ] Test 5.4: Update artifact
- [ ] Test 5.5: Delete artifact

### Message API
- [ ] Test 6.1: List messages
- [ ] Test 6.2: Send user message
- [ ] Test 6.3: Send assistant message
- [ ] Test 6.4: List messages after sending

### Integration Scenarios
- [ ] Scenario 7.1: Complete session lifecycle
- [ ] Scenario 7.2: Workflow approval flow
- [ ] Scenario 7.3: Artifact management

---

## Notes

- All session IDs in examples are placeholders
- Replace `{session_id}` with actual IDs from responses
- Windows users: use `%SESSION_ID%` for variable expansion
- Linux/Mac users: use `$SESSION_ID` for variable expansion
- The server supports CORS for frontend development

---

## Appendix: curl Options Reference

```bash
# Common options
-X METHOD        # HTTP method (GET, POST, PUT, DELETE)
-H "Key: Value"  # Add header
-d 'data'        # Request body data
-s               # Silent mode (no progress bar)
-v               # Verbose mode (show request/response)

# JSON handling
-H "Content-Type: application/json"  # Set JSON content type

# Windows-specific
Use single quotes for JSON, escape inner quotes: '{"key": "value"}'
```

---

**End of Manual Test Guide**
