"""
Templates for adding proper constraints to XML prompts.
Students will use these to enhance the problematic prompts.
"""

# Template 1: File processing with library and complexity constraints
CONSTRAINT_TEMPLATE_1 = """
<task>
Optimize file processing performance for large CSV files
</task>

<context>
Python application processing customer data exports
Current implementation reads entire files into memory
Files range from 100MB to 2GB in size
Performance bottleneck during peak processing times
</context>

<requirements>
- Reduce memory usage during file processing
- Improve processing speed for large files
- Maintain data integrity and error handling
- Support concurrent file processing
</requirements>

<constraints>
<allowed_libraries>
- pandas 1.5.3 (already pinned in requirements.txt)
- csv (Python standard library)
- multiprocessing and concurrent.futures (Python standard library)
- os, sys, pathlib (Python standard library)
- logging (use the application's existing logger configuration)
- Nothing else: adding a line to requirements.txt is out of scope
</allowed_libraries>

<forbidden_approaches>
- No package that is not already in requirements.txt, however popular
  (dask, polars, ray, modin, vaex, pyarrow are all unavailable)
- No package whose name you cannot verify on PyPI; if a faster reader is
  tempting, use pandas.read_csv(chunksize=...) instead
- No distributed compute frameworks (Spark, Celery workers, job schedulers)
- No microservice extraction: this stays one in-process function
- No Cython, C extensions, or compiled helpers: there is no build toolchain
- No intermediate database, object store, or temp-file cache layer
- No cloud services or external APIs
- Show the actual chunk-iteration code; do not hide the work behind a
  library call that is assumed to exist
</forbidden_approaches>

<complexity_limits>
- Modify the existing processing function; do not restructure the module
- Maximum 3 new functions, no new classes and no inheritance hierarchies
- Under 100 lines of new code in total
- Reuse the existing exception types and error-handling flow; do not
  introduce a new exception hierarchy
- No caching layer, no queue, and no worker abstraction beyond a plain
  multiprocessing.Pool
- Chunked reading is the expected approach; propose nothing larger
</complexity_limits>

<existing_environment>
- Python 3.9 on Linux, single machine, 8 GB RAM, 4 usable cores
- pandas 1.5.3 is pinned; treat requirements.txt as frozen
- No Docker, containerization, or cluster scheduler available
- Peak memory budget: under 500 MB per worker process
- The existing logging configuration and the CSV output column schema
  must both remain unchanged
</existing_environment>
</constraints>
"""

# Template 2: Simple logging with scope constraints  
CONSTRAINT_TEMPLATE_2 = """
<task>
Add logging to the discount calculation function
</task>

<context>
E-commerce application with simple pricing logic
Current function calculates customer discounts based on tier
Function is called frequently during checkout process
</context>

<requirements>
- Log when discount calculations occur
- Track discount amounts applied
- Enable debugging of pricing issues
</requirements>

<constraints>
<complexity_limits>
- Exactly 2 logging statements added inside the existing function
- No new functions, classes, modules, or files
- No new imports beyond the module's existing logger
- The function stays under 15 lines total
- Added logging overhead must stay under 1 ms per call
</complexity_limits>

<scope_boundaries>
- Only the discount calculation function is edited
- No changes to calling code, checkout flow, or error handling
- No changes to logging configuration, handlers, formatters, or levels
- No new dependencies and no changes to requirements.txt
- No metrics, tracing, or performance-monitoring instrumentation
- No database logging and no shipping logs to an external service
- Do not refactor or retest the surrounding pricing logic
</scope_boundaries>

<forbidden_approaches>
- No logging library beyond the standard library (no loguru, structlog,
  or any "advanced logging framework")
- No decorator or aspect-oriented wrapper around the function
- No abstract base classes, strategy pattern, observer pattern, or
  dependency injection for two log lines
- No configuration management system for log levels
- No structured/JSON logging, log correlation, or aggregation tooling
- No async, buffered, or queued log emission
</forbidden_approaches>

<preservation_requirements>
- Keep the function signature exactly as it is today
- Preserve the discount arithmetic and tier thresholds unchanged
- Preserve the return type and returned value for every input
- Keep existing exception behaviour identical, including error messages
- Leave the module's imports and overall structure as-is
- Checkout latency must be indistinguishable from current behaviour
</preservation_requirements>
</constraints>
"""

# Template 3: Notification system with platform constraints
CONSTRAINT_TEMPLATE_3 = """
<task>
Create user notification system for the mobile app
</task>

<context>
React Native mobile application
Backend API built with Node.js and Express
Currently uses basic email notifications
Need to add push notifications and in-app messages
</context>

<requirements>
- Send push notifications for important events
- Display in-app notifications for user actions
- Support different notification types and priorities
- Allow users to configure notification preferences
- Track notification delivery and engagement
</requirements>

<constraints>
<platform_constraints>
- One React Native codebase must serve both iOS and Android
- Push delivery must go through the push service already configured in the
  current app build; no SDK that forces a new native rebuild
- No native modules requiring custom native code
- Notification payloads must fit the 4 KB platform limit
- Added JavaScript bundle growth must stay under 1 MB
- Backend stays on the existing Node.js and Express version, and the
  existing middleware chain must keep working unchanged
</platform_constraints>

<existing_services>
- The Express API's existing JWT authentication middleware
- The existing /api/users endpoints and user schema, which is where
  notification preferences belong
- The existing primary database and its connection pool: no new datastore
- The existing email notification module, which stays as the fallback channel
- The existing REST URL versioning and JSON response envelope
- The React Native client's existing navigation and state management
</existing_services>

<forbidden_approaches>
- No message queues or brokers (Kafka, RabbitMQ, Redis Streams, SQS)
- No websocket or real-time layer (Socket.io, MQTT) for in-app messages;
  poll an existing-style REST endpoint instead
- No new third-party notification platform or push gateway SDK (Firebase
  Cloud Messaging, AWS SNS, OneSignal, Braze, Airship, Pusher), and no
  invented ones ("notification_master", "push_notification_pro")
- No microservice split: notifications live in the current API
- No event sourcing, CQRS, or state machines for delivery status
- No ML-driven send-time optimization and no analytics SDKs
- No npm package that is not already in package.json
</forbidden_approaches>

<integration_requirements>
- New notification routes sit under the existing API version prefix and
  return the existing error and success response format
- Every new route authorizes through the existing JWT middleware; no second
  auth path and no per-device token scheme
- Preferences persist on the existing user record via an additive migration
  with defaults, so current clients keep working
- Delivery and engagement tracking is stored in the existing database and
  read through the existing API, not a separate pipeline
- Client screens reuse the current navigation stack and state patterns
</integration_requirements>
</constraints>
"""

CONSTRAINT_GUIDANCE = {
    "allowed_libraries": {
        "purpose": "Explicitly list available dependencies to prevent phantom libraries",
        "examples": ["pandas (already installed)", "csv (standard library)", "multiprocessing (standard library)"],
        "pattern_prevention": "Eliminates phantom dependency pattern from Lesson 2"
    },
    "forbidden_approaches": {
        "purpose": "Prevent over-engineering and inappropriate solutions", 
        "examples": ["No microservices for simple tasks", "No external libraries not in requirements.txt", "No complex design patterns for simple functions"],
        "pattern_prevention": "Eliminates over-engineering pattern from Lesson 2"
    },
    "complexity_limits": {
        "purpose": "Set boundaries on solution scope and complexity",
        "examples": ["Maximum 20 lines of new code", "Single file modification only", "No new classes or abstractions"],
        "pattern_prevention": "Controls solution scope to prevent over-engineering"
    }
}

def display_constraint_templates():
    """Show constraint templates with guidance."""
    templates = [
        ("Template 1: File Processing Constraints", CONSTRAINT_TEMPLATE_1),
        ("Template 2: Simple Logging Constraints", CONSTRAINT_TEMPLATE_2),
        ("Template 3: Notification System Constraints", CONSTRAINT_TEMPLATE_3)
    ]
    
    print("=== CONSTRAINT ENHANCEMENT TEMPLATES ===\n")
    
    for title, template in templates:
        print(f"{title}:")
        print("-" * len(title))
        print(template.strip())
        print("\n" + "="*70 + "\n")

def display_constraint_guidance():
    """Show guidance for different constraint types."""
    print("=== CONSTRAINT TYPE GUIDANCE ===\n")
    
    for constraint_type, guidance in CONSTRAINT_GUIDANCE.items():
        print(f"{constraint_type.replace('_', ' ').title()}:")
        print(f"  Purpose: {guidance['purpose']}")
        print(f"  Examples: {', '.join(guidance['examples'])}")
        print(f"  Pattern Prevention: {guidance['pattern_prevention']}")
        print()

if __name__ == "__main__":
    display_constraint_templates()
    display_constraint_guidance()