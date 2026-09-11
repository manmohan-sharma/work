"""
Structured prompt templates for students to complete.

Students will use these templates to convert traditional prompts to structured format.
We'll use XML as our example format, but these principles work with any structured approach.
"""

# Structured Template 1: Basic structure for data processing prompt
XML_TEMPLATE_1 = """
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

# Structured Template 2: Caching enhancement template
XML_TEMPLATE_2 = """
<task>
[STUDENT TODO: Specific caching objective]
</task>

<context>
<current_system>
[STUDENT TODO: Describe existing API architecture]
</current_system>

<performance_baseline>
[STUDENT TODO: Current performance metrics if known]
</performance_baseline>
</context>

<requirements>
<functional_requirements>
[STUDENT TODO: What caching functionality is needed?]
- 
</functional_requirements>

<performance_requirements>
[STUDENT TODO: Specific performance targets]
- 
</performance_requirements>
</requirements>

<constraints>
[STUDENT TODO: Technical limitations, existing systems to work with]
- 
</constraints>
"""

# XML Template 3: Complex authentication system template  
XML_TEMPLATE_3 = """
<task>
[STUDENT TODO: Clear authentication system objective]
</task>

<context>
<existing_infrastructure>
[STUDENT TODO: Current database, user system, tech stack]
</existing_infrastructure>

<security_requirements>
[STUDENT TODO: Specific security standards to follow]
</security_requirements>
</context>

<requirements>
<authentication_features>
[STUDENT TODO: List each auth feature separately]
- 
- 
- 
</authentication_features>

<integration_requirements>
[STUDENT TODO: How it should work with existing systems]
- 
</integration_requirements>

<scalability_requirements>
[STUDENT TODO: Specific scalability needs]
- 
</scalability_requirements>
</requirements>

<constraints>
<forbidden_approaches>
[STUDENT TODO: What should NOT be used]
- 
</forbidden_approaches>

<technical_constraints>
[STUDENT TODO: System limitations]
- 
</technical_constraints>
</constraints>
"""

def display_xml_templates():
    """Display XML templates for student completion."""
    templates = [
        ("XML Template 1: Data Processing", XML_TEMPLATE_1),
        ("XML Template 2: API Caching", XML_TEMPLATE_2),
        ("XML Template 3: Authentication System", XML_TEMPLATE_3)
    ]
    
    print("=== XML PROMPT TEMPLATES ===\n")
    print("Replace [STUDENT TODO] sections with specific information from the traditional prompts.\n")
    
    for title, template in templates:
        print(f"{title}:")
        print("-" * 50)
        print(template.strip())
        print("\n" + "="*70 + "\n")

def get_student_completion_checklist():
    """Return checklist for students to verify their XML prompt completion."""
    return {
        "template_1": [
            "Task clearly specifies what kind of data processing is needed",
            "Context explains the system architecture and data types",
            "Requirements list specific functionality expected",
            "Constraints specify security measures and patterns to follow"
        ],
        "template_2": [
            "Task specifies exact caching objectives",
            "Context describes current API setup and performance baseline",
            "Requirements separate functional from performance needs",
            "Constraints specify integration requirements and limitations"
        ],
        "template_3": [
            "Task clearly states authentication system goals", 
            "Context provides infrastructure and security context",
            "Requirements break down complex functionality into specific features",
            "Constraints clearly separate forbidden approaches from technical limitations"
        ]
    }

if __name__ == "__main__":
    display_xml_templates()
    
    print("\n=== COMPLETION CHECKLIST ===")
    checklist = get_student_completion_checklist()
    for template, items in checklist.items():
        print(f"\n{template.replace('_', ' ').title()}:")
        for item in items:
            print(f"  ☐ {item}")