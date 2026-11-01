# demo-service

Deliberately outdated Express service. It only exists as a **scan target** for the remediation agent – never deploy it publicly.

The image is stored in Amazon ECR (`demo-service` repository, tags immutable) and scanned by Amazon Inspector (enhanced scanning), which reports **operating system and npm** vulnerabilities – see [ADR 0002](../../docs/adr/0002-amazon-inspector-as-finding-source.md).

The npm dependencies are pinned to outdated versions on purpose (`axios` has already been fixed once, see the [manual baseline run](../../docs/manual-run.md)). The base image must use an OS that Inspector still supports; for a discontinued one (e.g. Alpine 3.18) OS packages are no longer reported.

If the image is pushed as an image index (BuildKit), the tag shows `UNSUPPORTED_IMAGE` – Inspector scans the untagged child manifest. Check scan status and findings by that digest:

```bash
aws ecr describe-image-scan-findings --repository-name demo-service --image-id imageDigest=<digest> --profile inspector --region eu-north-1 --query imageScanStatus
```

## Build and push

Prerequisites: AWS CLI profile `inspector` (`aws login --profile inspector`), Docker running.

```bash
docker build -t <account-id>.dkr.ecr.eu-north-1.amazonaws.com/demo-service:<version> .
docker push <account-id>.dkr.ecr.eu-north-1.amazonaws.com/demo-service:<version>
```

On Windows the ECR token is too long for the Windows credential store. Use the ECR credential helper with a project-specific Docker config instead of `docker login`:

```powershell
$env:DOCKER_CONFIG = "$HOME\.docker-inspector"   # contains {"credHelpers": {"<registry>": "ecr-login"}}
aws configure export-credentials --profile inspector --format powershell | Invoke-Expression
```

## Delete an image

An image built with BuildKit is pushed as an image index plus untagged child manifests (image, attestation). Delete the index first, then the children – otherwise ECR rejects the request with `ImageReferencedByManifestList`. Images from the classic builder are a single manifest.

```bash
aws ecr describe-images --repository-name demo-service --profile inspector --region eu-north-1
aws ecr batch-delete-image --repository-name demo-service --image-ids imageDigest=<index-digest> --profile inspector --region eu-north-1
aws ecr batch-delete-image --repository-name demo-service --image-ids imageDigest=<child-digest> imageDigest=<child-digest> --profile inspector --region eu-north-1
```

## Lockfile

The lockfile is generated from the public npm registry only (see `.npmrc`):

```bash
npm install --package-lock-only --ignore-scripts
```
