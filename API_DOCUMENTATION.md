# RiskSafeAI API Documentation

## Base URL
```
http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com
```

**Note:** This is a permanent URL that will not change, even when the backend is updated.

---

## Authentication
Currently, no authentication is required. The API is publicly accessible.

---

## CORS
CORS is enabled for all origins (`*`). Your frontend can make requests from any domain.

---

## Endpoints

### 1. Health Check
**Purpose:** Verify the API is running

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "ok"
}
```

**Example (JavaScript):**
```javascript
fetch('http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/health')
  .then(response => response.json())
  .then(data => console.log(data));
```

---

### 2. Generate Compliance Obligation Register
**Purpose:** Generate a comprehensive compliance obligation register for Australian regulatory requirements

**Endpoint:** `POST /react/obligation_register`

**Request Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
  "query": "Your compliance question here"
}
```

**Example Queries:**
- `"What are the RG 209 obligations for personal loan providers?"`
- `"As a Head of Compliance for an Australian Fintech that provides a product Personal Loans. What are the must do statements in the Regulatory Guides relevant to the product?"`
- `"What are the prohibited actions for credit licensees?"`

**Response:**
```json
{
  "answer": "# COMPLIANCE OBLIGATION REGISTER\n\n## SECTION A: MANDATORY ACTIONS (\"MUST DO\")\n\n1. **Obligation Title**\n   - Verbatim Quote: \"...\"\n   - Source: RG 209.XX\n   - Context: ...\n\n## SECTION B: PROHIBITED ACTIONS (\"MUST NOT DO\")\n\n1. **Prohibition Title**\n   - Verbatim Quote: \"...\"\n   - Source: RG 209.XX\n   - Context: ...",
  "metadata": {
    "query": "Your original query",
    "timestamp": "2025-12-23T14:00:00Z",
    "sources_used": 15,
    "processing_time_seconds": 45.2
  }
}
```

**Response Time:**
- Simple queries: 10-30 seconds
- Complex obligation registers: 2-10 minutes
- **Maximum timeout: 66 minutes**

**Error Response:**
```json
{
  "detail": "Error message describing what went wrong"
}
```

**HTTP Status Codes:**
- `200 OK` - Success
- `400 Bad Request` - Invalid query (empty string)
- `500 Internal Server Error` - Processing error
- `504 Gateway Timeout` - Query took longer than 66 minutes (very rare)

---

## Frontend Integration Examples

### JavaScript (Fetch API)
```javascript
async function getComplianceRegister(query) {
  try {
    const response = await fetch(
      'http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/react/obligation_register',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: query })
      }
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error:', error);
    throw error;
  }
}

// Usage
getComplianceRegister("What are the RG 209 obligations?")
  .then(result => {
    console.log(result.answer);
    console.log('Metadata:', result.metadata);
  });
```

### React Example
```jsx
import { useState } from 'react';

function ComplianceSearch() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(
        'http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/react/obligation_register',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query })
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Request failed');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter your compliance question..."
          rows={4}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Processing...' : 'Generate Register'}
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      
      {result && (
        <div>
          <h2>Compliance Register</h2>
          <pre>{result.answer}</pre>
          <p>Sources used: {result.metadata.sources_used}</p>
          <p>Processing time: {result.metadata.processing_time_seconds}s</p>
        </div>
      )}
    </div>
  );
}
```

### Python Example
```python
import requests

def get_compliance_register(query):
    url = "http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/react/obligation_register"
    
    payload = {"query": query}
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=4000)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return None

# Usage
result = get_compliance_register("What are the RG 209 obligations?")
if result:
    print(result['answer'])
    print(f"Metadata: {result['metadata']}")
```

---

## Important Notes for Frontend Developers

### 1. Loading States
Always implement a loading indicator. Complex queries can take several minutes to process.

### 2. Timeout Handling
The API has a 66-minute maximum timeout. For very long queries, consider:
- Showing a progress indicator
- Allowing users to cancel the request
- Implementing client-side timeout if needed

### 3. Error Handling
Always handle errors gracefully:
- Network errors (no internet connection)
- HTTP errors (400, 500, 504)
- JSON parsing errors

### 4. Response Format
The `answer` field contains Markdown-formatted text. You may want to:
- Use a Markdown renderer (e.g., `marked.js`, `react-markdown`)
- Display it in a `<pre>` tag for plain text
- Parse and style the sections separately

### 5. Rate Limiting
Currently, there is no rate limiting, but be mindful of:
- Each query costs money (OpenAI API usage)
- Complex queries use significant resources
- Consider debouncing user input

---

## Testing

### Postman Collection
You can test the API using Postman:

1. **Health Check:**
   - Method: GET
   - URL: `http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/health`

2. **Obligation Register:**
   - Method: POST
   - URL: `http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/react/obligation_register`
   - Headers: `Content-Type: application/json`
   - Body (raw JSON):
     ```json
     {
       "query": "What are the RG 209 obligations?"
     }
     ```

### cURL Examples
```bash
# Health check
curl http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/health

# Obligation register
curl -X POST \
  http://risksafeai-alb-1805594549.ap-southeast-2.elb.amazonaws.com/react/obligation_register \
  -H 'Content-Type: application/json' \
  -d '{"query": "What are the RG 209 obligations?"}'
```

---

## Support & Contact

For technical issues or questions:
- Check the health endpoint first
- Review error messages in the response
- Contact: [Your Contact Information]

---

## Changelog

### Version 1.0 (2025-12-23)
- Initial release
- Obligation register generation
- CORS enabled
- 66-minute timeout support
