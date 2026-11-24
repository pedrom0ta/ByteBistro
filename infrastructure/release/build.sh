#!/usr/bin/env bash
set -euo pipefail

: "${RELEASE_TAG:?Set RELEASE_TAG to the tag of the source ZIP}"
if [[ "$RELEASE_TAG" == "release" ]]; then
    echo 'Set RELEASE_TAG to the tag of the source ZIP.' >&2
    exit 1
fi

release_dir=$(mktemp -d)
trap 'rm -rf -- "$release_dir"' EXIT

describe_image() {
    aws ecr describe-images --repository-name "$1" --image-ids "imageTag=$RELEASE_TAG" \
        --query 'imageDetails[0].imageDigest' --output text
}

publish() {
    local service="$1" repository="$2" context="$3"
    shift 3
    local repository_name="${repository#*/}" image="$repository:$RELEASE_TAG" digest
    if digest=$(describe_image "$repository_name" 2> "$release_dir/ecr-error"); then
        :
    elif grep -Fq '(ImageNotFoundException)' "$release_dir/ecr-error"; then
        docker build --platform linux/amd64 "$@" -t "$image" "$context"
        docker push "$image"
        digest=$(describe_image "$repository_name")
    else
        cat "$release_dir/ecr-error" >&2
        return 1
    fi
    if [[ ! "$digest" =~ ^sha256:[a-f0-9]{64}$ ]]; then
        echo "Invalid ECR image digest for $service." >&2
        return 1
    fi
    printf '%s\n' "$digest" > "$release_dir/$service.digest"
}

publish web "$WEB_REPOSITORY" apps/web
publish api "$API_REPOSITORY" apps/services --target api
publish worker "$WORKER_REPOSITORY" apps/services --target worker
aws s3 sync apps/web/static/ "s3://$ARTIFACT_BUCKET/static/" --only-show-errors

python3 - "$release_dir" <<'PY' > "$release_dir/release.json"
import json
from pathlib import Path
import sys

release_dir = Path(sys.argv[1])
print(json.dumps({
    service: (release_dir / f"{service}.digest").read_text().strip()
    for service in ("web", "api", "worker")
}))
PY
aws s3 cp "$release_dir/release.json" "s3://$ARTIFACT_BUCKET/releases/$RELEASE_TAG.json" --only-show-errors
