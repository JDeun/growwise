# Observed maintainer wiki validation

- Observed: 2026-11-03
- Environment: macOS arm64, Python 3.12.13
- Revision: modified working tree based on `5c92dac76c32a8910dee6461556354c822713d33`; exact new CLI/test hashes below.
- Fixture: public repository documents and synthetic temporary registries; no household records.
- Claim: offline provenance/history/candidate-boundary checks and existing docs/privacy tests executed. This is not a model, device-package or educational-effectiveness experiment.
- Limit: one PII-name denylist test skipped because the private denylist was not configured; structural privacy checks ran.

Command:

```bash
.venv/bin/python -m pytest tests/test_research_wiki.py tests/test_docs_code_consistency.py tests/test_repo_privacy_audit.py
```

Observed output:

```text
.................................................s                       [100%]
49 passed, 1 skipped in 2.40s
```

SHA256 of tested new logic:

```text
05ee8c76b377a768b2715686952326719c44edb92aa6ebc4b51ac5bf580005b8  scripts/research_wiki.py
0417522de159514a64faec97ff3e7442f459c1f9c7723fedc861c98f0db743f5  tests/test_research_wiki.py
```
