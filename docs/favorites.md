# Favorites contract

All routes require `Authorization: Bearer <accessToken>` and verify that the account still exists inside the operation's transaction. Responses use the existing error envelope. Successful responses disable HTTP caching.

| Method | Route | Result |
|---|---|---|
| GET | `/api/v1/users/me/favorites` | 200, ordered array of exercise objects with `isFavorite: true` and `sortOrder` |
| PUT | `/api/v1/users/me/favorites/{exercise_id}` | 204, append if absent; repeated addition preserves position |
| DELETE | `/api/v1/users/me/favorites/{exercise_id}` | 204, remove if present; repeated removal succeeds |
| PATCH | `/api/v1/users/me/favorites/reorder` | 204, replace the full order atomically |

Reorder body: `{"exerciseIds": ["<uuid>", "<uuid>"]}`. Send every current favorite exactly once. Duplicate IDs or malformed UUIDs produce 422. An incomplete or stale membership set produces 409 with no changes; refetch the list before retrying. An empty array succeeds only for an empty collection. Concurrent reorders of the same membership set use the last committed order.

Adding a nonexistent exercise produces 404. Removing a nonexistent favorite is a successful no-op. Missing/invalid access tokens and deleted accounts produce 401. No request accepts a user ID; ownership always comes from the authenticated subject.

The collection is returned in full so the client can submit its complete order. Positions start at zero and removal through the API compacts them. The public catalog remains independent of personalization; combine its IDs with this list when displaying favorite controls. The frontend service is not wired by this backend change.

## Persistence

Migration `0003` creates `user_favorites`. The composite primary key `(user_id, exercise_id)` prevents duplicate bookmarks. A unique `(user_id, sort_order)` constraint prevents duplicate positions; a check rejects negative positions. Both foreign keys cascade on deletion; an exercise index supports catalog deletion. Administrative catalog deletion can leave position gaps, without changing relative order; the next reorder/removal compacts them.

Services own transaction boundaries through a protocol. The SQLAlchemy adapter takes SQLite's write lock before reading membership or positions, so concurrent adds and reorders cannot overwrite partial state. Reordering first moves positions above the occupied range and then assigns the requested order in the same transaction; the immediate unique constraint remains active throughout. Any failure rolls everything back.

Catalog reseeding upserts stable IDs and preserves favorites. Downgrading to `0002` deliberately drops favorites while preserving accounts and exercises. Restoring the migration recreates an empty favorites table; take a backup before any production downgrade.

Tests exercise real migrations, schema drift, foreign keys and uniqueness, two-user isolation, deleted accounts, repeated requests, concurrent mutations, stale reorder rejection, rollback, and reseeding.
