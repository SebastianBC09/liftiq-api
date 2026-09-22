# Authentication API

All paths are prefixed with `/api/v1`. Requests use JSON and camelCase keys;
responses use camelCase. IDs are UUID strings. Auth/profile responses use
`Cache-Control: no-store`. No endpoint returns password hashes or token digests.

| Endpoint | Request | Success |
|---|---|---|
| `POST /auth/register` | Flat registration payload below | 201: user and tokens |
| `POST /auth/login` | `email`, `password` | 200: user and tokens |
| `POST /auth/refresh` | `refreshToken` | 200: replacement tokens |
| `POST /auth/logout` | `refreshToken` | 204, empty body |
| `GET /users/me` | `Authorization: Bearer <accessToken>` | 200: public user |

## Registration and login

```json
{
  "email": "person@example.com",
  "password": "choose-a-long-unique-password",
  "firstName": "Ada",
  "lastName": "Lovelace",
  "heightCm": 170.25,
  "weightKg": 65.5,
  "experienceLevel": "beginner",
  "goal": "technique"
}
```

The UI wizard submits one complete request. Every field is required. Extra
fields are rejected. Names are trimmed and must be 1–100 characters. Registration
passwords must be 8–128 characters; whitespace is preserved. Login accepts
1–128 characters and returns the same 401 for an unknown account or wrong password.
Email syntax is validated and addresses are normalized before lookup/storage.
Height/weight must be positive, below 10,000, with at most two decimal places;
these are the schema's storage bounds, not clinical guidance or finalized UI bounds.

Experience values: `beginner`, `intermediate`, `advanced`.
Goal values: `strength`, `hypertrophy`, `technique`, `general_fitness`.
Goal is stored without changing technique-scoring behavior.

Both successful registration and login return:

```json
{
  "accessToken": "<signed JWT>",
  "refreshToken": "<opaque random token>",
  "tokenType": "bearer",
  "expiresIn": 900,
  "user": {
    "id": "e331ffb2-fd59-4f24-a2cf-e1c6a80fb514",
    "email": "person@example.com",
    "firstName": "Ada",
    "lastName": "Lovelace",
    "heightCm": 170.25,
    "weightKg": 65.5,
    "experienceLevel": "beginner",
    "goal": "technique"
  }
}
```

`expiresIn` is the configured access-token lifetime in seconds (default 900).
Each login creates a new refresh-token family. Registration creates the user,
credential, and initial refresh record atomically and responds only after commit.
Duplicate normalized emails return 409; database uniqueness resolves races.

## Refresh and logout

```json
{"refreshToken": "<current opaque token>"}
```

Refresh returns `accessToken`, `refreshToken`, `tokenType`, and `expiresIn`;
it does not return `user`. The old refresh token becomes unusable and a replacement
is recorded in the same transaction. Replacements expire after the configured
refresh lifetime from issuance (default 30 days), so this is a sliding lifetime.
The raw refresh token is never stored in the database, only its SHA-256 digest.

Reusing a consumed token returns 401 and revokes all active tokens in that
user's family. This revocation is committed even though the response is an error.
Other login families and other users are unaffected. Consumed rows are retained
for detection; automated token-history cleanup is not part of this deliverable.

**The client must serialize refresh attempts.** Concurrent requests with the
same token yield at most one successful rotation. The other request counts as
reuse and revokes the successor as well. A lost refresh response cannot safely
be retried with the old token; require login again. There is no replay grace window.

Logout accepts the current token or a consumed ancestor and revokes the family.
Unknown tokens and repeated logout calls return 204. Structurally invalid requests
still return 422. Logout does not need a valid access token. Clearing local storage
alone does not revoke the server family; send logout first when connectivity permits.
Already-issued access tokens remain valid until their short expiry, unless the
user has been deleted. There is no access-token denylist.

On app restart, use the stored refresh token to obtain an access token, then fetch
`/users/me`. Keep access tokens in memory; use secure native storage for refresh
tokens. Browser credential storage remains a separate frontend design decision.

## Errors

```json
{"detail": "Could not validate credentials", "code": "unauthorized"}
```

Authentication failures return 401 with `WWW-Authenticate: Bearer`, including
expired/malformed access tokens, missing/deleted users, and invalid refresh tokens.
Duplicate registration returns 409 with code `conflict`.

```json
{
  "detail": "Request validation failed",
  "code": "validation_error",
  "errors": [{"field": ["body", "goal"], "code": "missing", "message": "Field required"}]
}
```

Validation returns 422. Field locations identify the input; submitted values and
Pydantic context are excluded. OpenAPI documents the actual error envelopes.

## Architecture and verification

HTTP handlers delegate to `AuthService`. Persistence and transaction behavior are
provided through focused protocols. The SQLAlchemy repository handles the auth
aggregate; only its unit-of-work adapter commits. Argon2id hashing/verification
runs outside the event loop and outside write transactions. Credential identity
and hash are rechecked after verification to catch intervening changes/deletion.

SQLite writes acquire `BEGIN IMMEDIATE` before reads. Refresh additionally uses
a conditional update to consume a still-active, unexpired token. Tests use
file-backed migrated databases and independent request sessions, including races
between refresh/refresh, register/register, and refresh/logout. Failure injection
verifies rollback when storing/signing tokens fails. No schema revision beyond
`0001` is needed for this phase.

No OAuth, password recovery, profile editing, frontend wiring, or new exercise
endpoints are included. Deployment remains a single-instance SQLite setup.
