"""
The three exercise prompts, rewritten in the structured format from xml_templates.py.

Each prompt keeps its original scenario (data processing, API caching, authentication)
but now carries the details AI needs: concrete task, system context, testable
requirements, and explicit constraints. Every requirements block also states what must
be preserved, which is the defense against the context gap pattern from Lesson 2.
"""

# Prompt 1: Data processing, converted to the flat four-tag structure
TRADITIONAL_PROMPT_1 = """
<task>
Add a validated, sanitized processing function for inbound user form submissions,
without changing how existing submissions are stored or reported.
</task>

<context>
Flask web application, PostgreSQL database accessed through the existing SQLAlchemy ORM layer.
User data arrives from three current forms: registration, profile update, and contact.
Field validation today is handled by the existing WTForms framework with custom validators.
Audit logging already exists via the app-wide structlog logger.
</context>

<requirements>
- Validate every incoming field against the schema declared for its form
- Sanitize string fields to block XSS and SQL injection before any database call
- Process validated input into the standardized dict shape the ORM models expect
- Return a (success, errors) response that names each field that failed validation
- Log every processing attempt (accepted and rejected) to the existing audit logger
- Handle malformed JSON and oversized payloads without raising to the request handler
- PRESERVE ALL EXISTING FUNCTIONALITY: current form endpoints, WTForms validators,
  ORM write paths, and audit log format must keep working unchanged
</requirements>

<constraints>
- Use the existing WTForms validators; do not reimplement field validation
- Follow current SQLAlchemy session and transaction patterns
- No external sanitization or validation libraries beyond the current stack
- Must stay backward compatible with the current API response contract
- Processing must complete under 200ms for a typical (< 50 field) submission
- Only server-side validation counts; client-side checks cannot be relied on
</constraints>
"""

# Prompt 2: API caching, converted with nested context and requirements sections
TRADITIONAL_PROMPT_2 = """
<task>
Add Redis read-through caching to the five highest-traffic GET endpoints,
leaving their request and response contracts and error handling untouched.
</task>

<context>
<current_system>
FastAPI application, PostgreSQL primary database, deployed as 4 uvicorn workers.
Endpoints in scope: /users/{id}, /profiles/{id}, /settings/{id}, /content/{id}, /analytics/{id}
Each request currently issues 2-4 ORM queries against the database on every call.
A Redis instance and connection pool already exist in the architecture, used today
only for rate limiting; existing auth and rate-limit middleware run before the handlers.
</current_system>

<performance_baseline>
Median response time: 300ms; 95th percentile: 800ms; range 200-500ms per endpoint.
The current read/write mix is roughly 90% GET, so a 70-80% hit rate is realistic.
Target: under 50ms on a cache hit, no worse than the existing 300ms median on a miss.
</performance_baseline>
</context>

<requirements>
<functional_requirements>
- Cache GET responses for the five endpoints listed above, keyed per resource id
- Invalidate the affected keys on every POST, PUT, PATCH, and DELETE to that resource
- Handle cache misses and Redis outages by falling back to the current database path
- Support a per-endpoint TTL (profiles 5min, settings 15min, content 1hr, analytics 1min)
- Return the same serialized payload on a hit that the uncached handler would produce
- PRESERVE ALL EXISTING FUNCTIONALITY: auth middleware, rate limiting, request
  validation, error responses, and structured request logging must be unchanged
</functional_requirements>

<performance_requirements>
- Median response time must drop under 50ms for cache hits
- Cache-miss latency must not regress beyond the current 300ms median
- Must support 1000+ concurrent requests with no increase in error rate
- Cache hit rate should hold above 70% within 24 hours of deployment
- Total cache memory footprint must stay under 1GB
</performance_requirements>
</requirements>

<constraints>
- Use the existing Redis connection pool; do not open new connections per request
- No changes to endpoint paths, function signatures, or response schemas
- Must run inside the current middleware ordering, after authentication
- No caching libraries beyond the redis-py client already in requirements.txt
- Cache keys must carry a tenant prefix so keys cannot collide across tenants
- A Redis failure must never surface as a 5xx to the client
</constraints>
"""

# Prompt 3: Authentication system, converted with requirements and constraints broken out
TRADITIONAL_PROMPT_3 = """
<task>
Replace the current plain-password login with a hashed-credential authentication
system covering login, logout, and password reset, built on the existing user database.
</task>

<context>
<existing_infrastructure>
Node.js/Express application, MongoDB users collection, React SPA front end.
Existing user schema: {_id, email, password, profile, created_at, last_login}
Passwords are currently stored in plain text, which is the defect driving this work.
The current Express middleware chain is cors, helmet, body-parser, then route handlers.
An email service (SendGrid wrapper) already exists and is used for notifications.
</existing_infrastructure>

<security_requirements>
- bcrypt password hashing with a minimum of 12 salt rounds
- Rate limiting of 5 authentication attempts per IP per minute
- JWT access tokens with 30-minute expiry plus a refresh token flow
- Server-side validation and sanitization on every auth endpoint
- Password reset tokens that are single-use and expire within 1 hour
</security_requirements>
</context>

<requirements>
<authentication_features>
- Login must verify email and password against the bcrypt hash and issue a JWT
- Logout must invalidate the active token and clear the server-side session record
- Password reset must email a time-limited token and require it to set a new password
- Failed logins must be counted per account and lock the account after 10 attempts
- Token refresh must issue a new access token without a second password prompt
- PRESERVE ALL EXISTING FUNCTIONALITY: profile endpoints, settings endpoints, and
  the React app's current auth flow must keep working through the migration
</authentication_features>

<integration_requirements>
- Must work with the existing MongoDB connection and users collection
- Must slot into the current Express middleware chain without reordering it
- Must migrate existing plain-text passwords to hashes on each user's next login
- Must use the existing email service for reset messages, not a new provider
- Must keep the current user profile document structure intact
</integration_requirements>

<scalability_requirements>
- Must handle 1000+ concurrent authentication requests
- Token validation must work across multiple server instances with no shared memory
- Auth lookups must use an indexed query on the email field
- Session and token records must survive a server restart
- Expired tokens and reset codes must be cleaned up on a schedule
</scalability_requirements>
</requirements>

<constraints>
<forbidden_approaches>
- No external authentication services (Auth0, Firebase Auth, Okta)
- No third-party OAuth providers in this implementation
- No plain-text password storage anywhere, including logs
- No client-side-only validation
- No storing tokens in localStorage
</forbidden_approaches>

<technical_constraints>
- Use only the existing MongoDB driver and Express version; no framework swap
- JWT signing secret must come from an environment variable, never hardcoded
- No breaking changes to existing profile or settings endpoints
- Must follow the current error response format for all auth failures
- Cannot add a new datastore; session state must live in MongoDB or the existing Redis
</technical_constraints>
</constraints>
"""

# Problems in the original unstructured prompts that these structured versions resolve:
EXPECTED_PROBLEMS = {
    "prompt_1": [
        "AI doesn't know what kind of data processing is needed",
        "Security requirements are vague",
        "No specific patterns are mentioned",
        "Function signature and return type are undefined"
    ],
    "prompt_2": [
        "No specific performance targets given",
        "Current setup is not described",
        "Caching strategy unspecified",
        "No constraints on cache backends mentioned"
    ],
    "prompt_3": [
        "Multiple requirements buried in run-on sentence",
        "Security best practices not specified",
        "Database integration details missing",
        "Scalability requirements unclear",
        "Constraint about external services buried at the end"
    ]
}

def display_traditional_prompts():
    """Display the structured prompts and the original problems each one resolves."""
    prompts = [
        ("Prompt 1: Secure Data Processing", TRADITIONAL_PROMPT_1),
        ("Prompt 2: API Caching with Redis", TRADITIONAL_PROMPT_2),
        ("Prompt 3: Authentication System", TRADITIONAL_PROMPT_3)
    ]

    print("=== STRUCTURED PROMPTS ANALYSIS ===\n")

    for i, (title, prompt) in enumerate(prompts, 1):
        print(f"{title}:")
        print("-" * 50)
        print(prompt.strip())
        print("\nProblems from the original prompt that this structure resolves:")
        for problem in EXPECTED_PROBLEMS[f"prompt_{i}"]:
            print(f"  • {problem}")
        print("\n" + "="*70 + "\n")

if __name__ == "__main__":
    display_traditional_prompts()
