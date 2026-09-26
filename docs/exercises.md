# Exercise catalog

`GET /api/v1/exercises` returns a public array sorted by name, then ID. Optional
query parameters: `muscle_group` (chest, back, legs, shoulders, biceps, triceps,
core), `limit` (1–100, default 100), and `offset` (nonnegative, default 0).
`GET /api/v1/exercises/{id}` returns one exercise or 404; malformed UUIDs and
invalid filters return 422. Responses use camelCase fields and UUID strings.

The catalog has no user-specific favorite state. Clients obtain that separately
from the favorites API when available. Content includes name, slug, muscleGroup,
difficulty, description, instructions, commonMistakes, primaryMuscles,
secondaryMuscles, and optional media URLs. No unlicensed media is bundled.

## Seed and migration

```bash
uv run --locked alembic upgrade head
uv run --locked python -m scripts.seed_exercises
# Container with migrations already applied:
docker compose exec api python -m scripts.seed_exercises
```

Revision `0002` creates the table and indexes. Seeding is a separate explicit
operation; startup never silently overwrites the catalog. The bundled JSON has
35 exercises, five per muscle group, with original concise Spanish descriptions.
[ACE's exercise library](https://www.acefitness.org/resources/everyone/exercise-library/)
is a reference for exercise nomenclature; the text and media are not copied
from that library.

The seed validates the entire file before writing. Stable UUIDv5 IDs derive from
`https://liftiq.app/exercises/{slug}`; changing a slug is an identity change and
must be reviewed. A transaction updates known seed IDs without changing their
references or deleting additional exercises. Repeating the command does not
create duplicates. Validation/write failure rolls back the operation.
Downgrading to `0001` deletes the catalog but preserves accounts; reseed after
re-upgrading. Back up existing data before schema changes.

## Analysis metadata

`analysisSupported` is false for all bundled entries. `jointAngles` is empty,
`requiredKeypoints` is empty, and `analysisVersion`/`cameraView` are null. Being
in the catalog does not mean technique scoring or repetition counting has been
validated for that exercise, particularly isometric holds such as planks.

The typed contract supports future validated configurations:

- Each named joint angle has finite `min`, `max`, and `ideal` values in degrees,
  with `0 <= min <= ideal <= max <= 180`.
- `landmarks` contains three distinct BlazePose landmark names, with the vertex
  in the middle. Each must appear in `requiredKeypoints`.
- Required keypoints cannot repeat. Supported analysis requires nonempty angle
  definitions, a positive version, and cameraView `front` or `side`.

These checks establish structural consistency, not biomechanical validity.
Enable analysis only after agreeing on coordinate conventions, phase-dependent
rules, and validation with the client analysis implementation. The seed does not
invent universal joint thresholds. Persisted content is validated again when read.
