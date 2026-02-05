# Jayden API Reference

## Overview

The Jayden REST API allows developers to programmatically interact with the Jayden platform. Use the API to manage conversations, query analytics, control the voice assistant, manage your knowledge base, and integrate Jayden into your custom applications and workflows.

**Base URL**: `https://api.Jayden.com/v1`

**API Version**: v1 (current), v0 (deprecated, sunset date: March 2026)

**Availability**: Pro and Enterprise plans only. Starter plan customers can upgrade to access API features.

## Authentication

All API requests must include an API key in the `Authorization` header.

```
Authorization: Bearer tk_live_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

API keys can be generated in the Jayden dashboard under **Settings > API Keys**. You can create multiple keys with different permission scopes.

**Key Types**:
- `tk_live_*` -- Production API keys with full access
- `tk_test_*` -- Sandbox API keys for development and testing (no charges incurred)

**Security Best Practices**:
- Never expose API keys in client-side code or public repositories
- Rotate keys regularly (recommended: every 90 days)
- Use the minimum required permission scope for each key
- Use test keys during development

## Rate Limits

| Plan | Monthly Limit | Burst Rate |
|------|--------------|------------|
| Pro | 10,000 calls/month | 100 requests/minute |
| Enterprise | Custom (default 100,000) | 500 requests/minute |

Rate-limited responses return HTTP `429 Too Many Requests` with headers:
- `X-RateLimit-Limit`: Your rate limit
- `X-RateLimit-Remaining`: Remaining requests
- `X-RateLimit-Reset`: Unix timestamp when the limit resets
- `Retry-After`: Seconds to wait before retrying

## Core Endpoints

### Conversations

#### List Conversations
```
GET /conversations
```

Query parameters:
- `status` (string): Filter by status -- `active`, `completed`, `escalated`
- `channel` (string): Filter by channel -- `voice`, `chat`, `sms`, `whatsapp`
- `from` (ISO 8601): Start date filter
- `to` (ISO 8601): End date filter
- `limit` (integer, default 20, max 100): Number of results
- `offset` (integer, default 0): Pagination offset

**Response** (200 OK):
```json
{
  "data": [
    {
      "id": "conv_abc123",
      "status": "completed",
      "channel": "voice",
      "duration_seconds": 145,
      "language": "en-US",
      "sentiment_score": 0.82,
      "created_at": "2025-01-15T10:30:00Z",
      "ended_at": "2025-01-15T10:32:25Z"
    }
  ],
  "total": 1250,
  "limit": 20,
  "offset": 0
}
```

#### Get Conversation Detail
```
GET /conversations/{conversation_id}
```

Returns full conversation details including transcript, detected intents, sentiment timeline, and metadata.

#### Get Conversation Transcript
```
GET /conversations/{conversation_id}/transcript
```

Returns the full conversation transcript with timestamps, speaker labels, and confidence scores.

### Appointments

#### Create Appointment
```
POST /appointments
```

Request body:
```json
{
  "calendar_id": "cal_xyz789",
  "title": "Product Demo",
  "start_time": "2025-02-10T14:00:00Z",
  "duration_minutes": 30,
  "attendee_email": "customer@example.com",
  "attendee_name": "Jane Smith",
  "notes": "Interested in Enterprise plan features"
}
```

**Response** (201 Created):
```json
{
  "id": "apt_def456",
  "calendar_id": "cal_xyz789",
  "title": "Product Demo",
  "start_time": "2025-02-10T14:00:00Z",
  "end_time": "2025-02-10T14:30:00Z",
  "status": "confirmed",
  "google_event_id": "google_evt_abc",
  "created_at": "2025-01-15T10:35:00Z"
}
```

#### List Appointments
```
GET /appointments
```

#### Get Appointment
```
GET /appointments/{appointment_id}
```

#### Update Appointment
```
PATCH /appointments/{appointment_id}
```

#### Cancel Appointment
```
DELETE /appointments/{appointment_id}
```

#### Check Availability
```
GET /availability
```

Query parameters:
- `calendar_id` (required): The calendar to check
- `date` (required, YYYY-MM-DD): The date to check
- `duration_minutes` (required): Desired appointment length
- `timezone` (optional, default UTC): IANA timezone string

### Knowledge Base

#### List Documents
```
GET /knowledge-base/documents
```

#### Upload Document
```
POST /knowledge-base/documents
```

Accepts `multipart/form-data` with the document file. Supported formats: `.md`, `.pdf`, `.docx`, `.html`, `.csv`, `.txt`.

#### Delete Document
```
DELETE /knowledge-base/documents/{document_id}
```

#### Search Knowledge Base
```
POST /knowledge-base/search
```

Request body:
```json
{
  "query": "What are the pricing plans?",
  "top_k": 5,
  "min_relevance_score": 0.7
}
```

Returns the top matching document chunks with relevance scores, useful for testing your RAG configuration.

### Analytics

#### Get Summary Metrics
```
GET /analytics/summary
```

Query parameters:
- `from` (required): Start date
- `to` (required): End date
- `granularity` (optional): `hour`, `day`, `week`, `month`

Returns aggregated metrics including total interactions, resolution rate, average handle time, CSAT score, and escalation rate.

#### Get Sentiment Report
```
GET /analytics/sentiment
```

#### Get Topic Distribution
```
GET /analytics/topics
```

### Webhooks

#### List Webhook Subscriptions
```
GET /webhooks
```

#### Create Webhook Subscription
```
POST /webhooks
```

Request body:
```json
{
  "url": "https://your-server.com/webhook",
  "events": ["conversation.ended", "appointment.created"],
  "secret": "your_webhook_secret"
}
```

The `secret` is used to sign webhook payloads with HMAC-SHA256. Verify the `X-Jayden-Signature` header to ensure webhook authenticity.

## Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "code": "invalid_request",
    "message": "The 'start_time' field must be a valid ISO 8601 timestamp.",
    "param": "start_time",
    "request_id": "req_abc123"
  }
}
```

Common error codes:

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `invalid_request` | Request body or parameters are invalid |
| 401 | `unauthorized` | Missing or invalid API key |
| 403 | `forbidden` | API key lacks required permissions |
| 404 | `not_found` | Requested resource does not exist |
| 429 | `rate_limited` | Rate limit exceeded |
| 500 | `internal_error` | Unexpected server error |

## SDKs and Libraries

Official SDKs are available for popular languages:
- **Python**: `pip install Jayden` ([GitHub](https://github.com/Jayden/Jayden-python))
- **Node.js**: `npm install @Jayden/sdk` ([GitHub](https://github.com/Jayden/Jayden-node))
- **Go**: `go get github.com/Jayden/Jayden-go`
- **Ruby**: `gem install Jayden`

Community-maintained SDKs are also available for Java, C#, and PHP.
