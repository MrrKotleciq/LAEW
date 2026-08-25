# LAEW Tool Contract — Web

## 1. Overview
- **Category**: `web`
- **Domain**: External technical documentation retrieval, API reference lookups, and web search.
- **Specification Version**: 1.0

---

## 2. Security Enforcement (Below Model Layer — Principle P8)

1. **Read-Only Scope**:
   - The web toolset is strictly read-only. No POST/PUT mutations, file uploads, or remote execution endpoints are permitted.
2. **Protocol Restrictions**:
   - Only standard `http://` and `https://` protocols are allowed. `file://`, `ftp://`, or custom protocols are blocked.
3. **Secret Protection**:
   - Headers, query parameters, and fetched payloads MUST NOT transmit local workspace secrets, keys, or `.env` contents.

---

## 3. Operations

### 3.1. `search_web`
Queries search engines for technical documentation, specifications, and libraries.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `query` (string, required): Search query string.
  - `domain` (string, optional): Preferred domain constraint (e.g., `docs.rs`, `github.com`).
- **Outputs**:
  - `results` (array of objects):
    - `title` (string): Result title.
    - `url` (string): Direct URL.
    - `snippet` (string): Summary snippet.

---

### 3.2. `read_url_content`
Fetches and converts public technical documentation or web page text to Markdown.

- **Type**: `Read-Only`
- **User Approval Required**: `No`
- **Inputs**:
  - `url` (string, required): HTTP/HTTPS URL to fetch.
- **Outputs**:
  - `status_code` (integer): HTTP response status.
  - `content_markdown` (string): Clean Markdown converted from page content.
  - `title` (string, optional): Page title.
- **Error Codes**:
  - `ERR_INVALID_PROTOCOL`: Attempted to fetch unsupported protocol scheme.
  - `ERR_FETCH_FAILED`: Network error, non-200 status, or timeout.
