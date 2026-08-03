# Local Qdrant and dense embedding runbook

This stack is for local development and tests only. It binds all exposed ports to
loopback and has no production deployment path.

## Prerequisites

Install Docker Compose and prepare a local Hugging Face cache that already contains
the exact RuBERT revision `e8ed3b0c8bbf4fb6984c3de043bf7d2f4e5969ae`. The embedding
container is offline and will not download a model.

Set secrets only in the current shell; do not add them to a file or Git:

```bash
export QDRANT_API_KEY='replace-with-a-local-dev-secret'
export HF_MODEL_CACHE="$PWD/.cache/huggingface"
docker compose -f compose.qdrant.yml up --build -d
```

Check service health locally:

```bash
curl --fail http://127.0.0.1:8080/healthz
curl --fail -H "api-key: $QDRANT_API_KEY" http://127.0.0.1:6333/healthz
```

## Collection and snapshots

All scripts reject a missing API key and non-loopback Qdrant URL. They default to
the `stage_embeddings` collection with the 312-dimensional cosine vectors used by
the pinned local encoder.

```bash
deploy/qdrant/scripts/create-collection.sh
deploy/qdrant/scripts/snapshot.sh
QDRANT_RESTORE_CHECK=1 deploy/qdrant/scripts/restore-check.sh
```

The restore check creates and deletes a disposable local collection. It does not
touch `stage_embeddings`. The Qdrant Docker volume persists data across container
restarts; remove it only when intentionally resetting local development data:

```bash
docker compose -f compose.qdrant.yml down
```

To reset data (destructive), explicitly remove the `qdrant_storage` volume after
listing it with `docker volume ls`.

## Troubleshooting

If embeddings return `model_unavailable`, verify that `HF_MODEL_CACHE` is mounted
and contains the pinned revision. The service never logs submitted text. A 503
means the model or local embedding service is unavailable; inputs are not retried
automatically.
