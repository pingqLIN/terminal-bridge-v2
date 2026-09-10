# Repository Structure

Find files by purpose. Package and existing public documentation paths remain stable.

```text
terminal-bridge-v2/
├── README.md / README.zh-TW.md
├── tb2/                 # Python runtime and CLI
├── tests/               # Regression and integration tests
├── schemas/             # Machine-readable contracts
├── examples/            # Example configurations and fixtures
├── tools/               # Diagnostics and development utilities
├── deploy/              # Deployment templates
├── docs/
│   ├── README.md / README.zh-TW.md
│   ├── getting-started*.md
│   ├── role-guides*.md
│   ├── validation-status*.md
│   ├── platforms/
│   └── images/
│       └── kindergarten/
└── .github/             # CI and community templates
```

## Maintenance rules

- Keep user guides in docs and link them from the index; align English and Traditional Chinese.
- Put platform specifics in platforms and image series beneath images.
- Keep schemas and reusable examples at their established paths to preserve runtime references.
- Update navigation before renaming documents with external consumers.
- Keep local evidence, backups, internal plans, and raw prompts in Git-ignored storage; avoid blanket git add operations.
- Before a public push, review an explicit file list, diffs, links, sensitive content, and tests. Ignore rules do not exclude already tracked files.

[Back to documentation](README.md)
