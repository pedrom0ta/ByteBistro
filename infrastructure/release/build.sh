#!/usr/bin/env bash
set -euo pipefail

publish() {
    local service="$1" repository="$2" context="$3"
    shift 3
    local repository_name="${repository#*/}" image="$repository:$RELEASE_TAG"
    if ! aws ecr describe-images --repository-name "$repository_name" --image-ids "imageTag=$RELEASE_TAG" >/dev/null 2>&1; then
        docker build "$@" -t "$image" "$context"
        docker push "$image"
    fi
    aws ecr describe-images --repository-name "$repository_name" --image-ids "imageTag=$RELEASE_TAG" \
        --query 'imageDetails[0].imageDigest' --output text > "/tmp/bytebistro-$service.digest"
}

publish web "$WEB_REPOSITORY" client
publish api "$API_REPOSITORY" backend --target api
publish worker "$WORKER_REPOSITORY" backend --target worker
aws s3 sync client/static/ "s3://$ARTIFACT_BUCKET/static/" --only-show-errors

python3 - <<'PY' > /tmp/bytebistro-release.json
import json
from pathlib import Path

print(json.dumps({
    service: Path(f"/tmp/bytebistro-{service}.digest").read_text().strip()
    for service in ("web", "api", "worker")
}))
PY
aws s3 cp /tmp/bytebistro-release.json "s3://$ARTIFACT_BUCKET/releases/$RELEASE_TAG.json" --only-show-errors
