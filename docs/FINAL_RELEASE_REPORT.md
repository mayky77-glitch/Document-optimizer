# Final release report — Block 18

| Area | Status | Evidence |
|---|---|---|
| Block 17 acceptance | PASS | PR #17; CI `30575326764`; main CI `30575425467`; SHA `322cb9ce08f14c017dbdc3bf16c5b91b33238e63` |
| Block 17 full real+slow | PASS | 569 passed in 92.84s |
| Block 18 tests/model smoke | NOT RUN | Evidence not supplied |
| Clean installs | NOT RUN | Evidence not supplied |
| Block 18 PR/CI | NOT RUN | Evidence not supplied |

Block 18 remains in progress. Its optional local RAG pins
`cointegrated/rubert-tiny2` revision `e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae`
(29.4M parameters, 312 dimensions, Russian), with lazy local loading,
normalized cosine retrieval and deterministic top-k/tie ordering. Unavailable
dependency/model is controlled; Block 12 rules remain authoritative and
semantic-only relations require manual review.

Owner evidence is required before declaring Block 18 released.
