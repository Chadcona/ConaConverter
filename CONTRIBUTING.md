# Contributing to ConaConverter

Thanks for your interest in contributing! ConaConverter is a community project and all contributions are welcome — whether that's bug fixes, new format support, UI improvements, or documentation.

---

## Getting started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ConaConverter.git
   cd ConaConverter
   ```
3. **Install dev dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```
4. **Run the tests** to confirm everything is working:
   ```bash
   pytest
   ```
5. **Create a branch** for your change:
   ```bash
   git checkout -b feature/my-change
   ```

---

## Types of contributions

### Bug reports

Open an issue and include:
- OS and Python version
- The source and target DJ software
- The file you were trying to convert (if you can share it, or a description of its structure)
- The full error message or unexpected behaviour

### Bug fixes

- Link your PR to the relevant issue
- Add or update a test that would have caught the bug

### New format support

Adding a new DJ platform (e.g. Traktor):

1. Create `conaconverter/converters/myformat.py` with `MyFormatReader(BaseReader)` and `MyFormatWriter(BaseWriter)`
2. Register in `conaconverter/converters/__init__.py`
3. Add detection logic in `conaconverter/detector.py`
4. Add a label to `FORMAT_LABELS`
5. Add a fixture file in `tests/fixtures/` and tests in `tests/test_myformat.py`
6. Document the format in `docs/FORMAT_NOTES.md`

### UI improvements

The UI lives in `conaconverter/ui/`. Keep it minimal and functional — the goal is to stay out of a DJ's way, not to add features for their own sake.

### Documentation

Corrections, clarifications, and additions to `README.md`, `docs/DEVELOPMENT.md`, or `docs/FORMAT_NOTES.md` are always welcome.

---

## Code standards

- **Python 3.10+** compatible
- **PEP 8** style
- **Type hints** on public functions and methods
- **No new external dependencies** for core parsing logic — use stdlib (`xml.etree`, `sqlite3`, `zlib`, `struct`) where possible
- **Tests required** for any new reader/writer — minimum: read test + round-trip test

---

## Running tests

```bash
pytest                          # all tests
pytest -v                       # verbose
pytest tests/test_rekordbox.py  # single file
pytest -k "round_trip"          # filter by name
```

Tests are designed to run without any DJ software installed. All fixtures are synthetic files in `tests/fixtures/`, and Engine OS tests use in-memory SQLite databases.

---

## Pull requests

- Keep PRs focused — one feature or fix per PR
- Write a clear PR description explaining what changed and why
- All existing tests must pass
- New code should have tests

---

## Questions

Open a [GitHub Discussion](https://github.com/Chadcona/ConaConverter/discussions) for anything that isn't a bug or feature request.
