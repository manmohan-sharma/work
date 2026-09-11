# Concept 2: Authentication Security Review

## Exercise Overview

Review an authentication system for security and structural issues. Apply systematic code review skills to identify potential problems with security, architecture, and implementation.

## Learning Objectives

- Apply systematic security analysis
- Identify authentication implementation issues
- Recognize structural and coupling problems
- Practice security-focused code review

## Instructions

### Step 1: Run Tests to See the Issues
```bash
cd concept2-authentication-security-review/starter
pytest test_security_vulnerabilities.py -v
```

**Expected Output:**
- Basic functionality tests pass
- Security tests reveal potential issues
- Tests demonstrate various authentication patterns

### Step 2: Security Review
1. **Open** `starter/user_auth.py` and examine the security flaws
2. **Focus on security issues** - this is a security-critical component
3. **Apply** the engineering framework with extra attention to:
   - SQL injection vulnerabilities (line 27!)
   - Password handling (plain text storage!)
   - Input validation (none!)
   - Error handling

### Step 3: Run Security Tests on Secure Solution
```bash
cd ../solution
pytest test_secure_authentication.py -v
```

**Expected Output:**
- All security tests pass
- SQL injection attempts are blocked
- Passwords are properly hashed
- Input validation works correctly

### Step 4: Document Security Issues
4. **Document** all security vulnerabilities found
5. **Compare** with the secure implementation

## Review Template

### Critical Security Issues

**SQL Injection:**
- [ ] Issue: [SQL injection via string concatenation..line 27]
- [ ] Impact: [Complete database compromise]
- [ ] Fix: [Use parameterized queries to prevent SQL injection]

**Password Security:**
- [ ] Issue: [two known password are hardcoded into the production import path and ther is no password policy]
- [ ] Risk Level: Critical
- [ ] Recommendation: [Hash passwords with strong algorithms (PBKDF2, bcrypt, Argon2)]

**Input Validation:**
- [ ] Missing validation: [password.encode() is called unguarded]
- [ ] Attack vector: [An unauthenticated caller can crash the login handeler at will with one request]

### Structural Issues

**Code Architecture:**
- [ ] Coupling issues: [__init__ builds its own dependency via the global connect_to_database() with a hardcoded :memory: DB (:24-25), so the class can't be tested or given a real/pooled connection without monkeypatching]
- [ ] Separation of concerns: [one 69-line module mixes schema, fixture seeding, connection management and auth; self.db_connection is public (:25) and SELECT * + user[2] couples login to column order (:29,:35)]

**Error Handling:**
- [ ] Information leakage: [253 ms known vs 0 ms unknown user is an enumeration oracle, uncaught exceptions return stack traces, and no audit logging means failures and attacks are invisible]
- [ ] Missing error cases: [login() has no try/except — unhandled bad input, sqlite3.Error, and a malformed/NULL stored hash (checkpw raises), plus no rate limiting or lockout against brute force]

### Overall Security Assessment

- **Security Rating:** Critical Risk
- **Primary Concerns:** [1) predictable session tokens — random.choice is not a CSPRNG (:68); 2) hardcoded admin/password123 credentials in the production path (:56-61); 3) no session management — token never stored, expired or revocable (:37)]
- **Recommendation:** Reject
- **Immediate Actions Required:** [swap random→secrets.token_urlsafe, remove seeded credentials, add a persisted+expiring session store with logout, inject the DB connection, and validate input so login() returns None instead of raising]

## Critical Vulnerabilities to Find

1. **SQL Injection** via string concatenation in database queries
2. **Plain text password storage** and comparison
3. **No input validation** allowing malicious input
4. **Information disclosure** through error messages
5. **Tight coupling** between database and authentication logic

## Security Best Practices (from Solution)

- Use parameterized queries to prevent SQL injection
- Hash passwords with strong algorithms (PBKDF2, bcrypt, Argon2)
- Implement proper input validation and sanitization
- Use dependency injection for better testing and security
- Add rate limiting to prevent brute force attacks
- Implement proper session management
- Add comprehensive audit logging

## Real-World Impact

The vulnerabilities in this code could lead to:
- Complete database compromise
- User account takeovers
- Data breaches
- Credential theft
- System-wide security failures

After your review, examine the solution to understand how to implement secure authentication with proper password hashing, parameterized queries, and comprehensive security measures.