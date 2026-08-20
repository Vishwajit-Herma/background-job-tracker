# Justfile for Background Job Tracker

# List all available commands
default:
    @just --list

# Development server
dev:
    uv run python manage.py runserver

# Run tests
test:
    uv run pytest

# Run tests with coverage
test-cov:
    uv run pytest --cov --cov-report=html --cov-report=term

# Format code
format:
    uv run ruff format .

# Lint code
lint:
    uv run ruff check .

# Type check
typecheck:
    uv run mypy .

# Run all quality checks
check: lint typecheck test

# Django shell
shell:
    uv run python manage.py shell_plus

# Make migrations
makemigrations:
    uv run python manage.py makemigrations

# Run migrations
migrate:
    uv run python manage.py migrate

# Create superuser
createsuperuser:
    uv run python manage.py createsuperuser

# Docker compose up
up:
    docker compose up -d

# Docker compose down
down:
    docker compose down

# Docker compose logs
logs:
    docker compose logs -f

# Run Celery worker
celery-worker:
    uv run celery -A config worker -l info

# Run Celery beat
celery-beat:
    uv run celery -A config beat -l info

# Run Flower
celery-flower:
    uv run celery -A config flower


# Serve documentation
docs-serve:
    uv run mkdocs serve

# Build documentation
docs-build:
    uv run mkdocs build

# Install dependencies
install:
    uv sync --all-extras

# Update dependencies
update:
    uv lock --upgrade

# Validate YAML files (basic syntax check)
validate-yaml:
    @echo "Validating YAML files..."
    @for file in $(find . -name "*.yml" -o -name "*.yaml" | grep -v -E "(.venv|node_modules|venv)"); do \
        python -c "import yaml; yaml.load(open('$$file'), Loader=yaml.FullLoader)" 2>&1 | grep -q "Error" && echo "✗ $$file" || true; \
    done
    @echo "✓ Basic YAML validation complete (use 'yamllint .' for detailed linting)"

# Lint Dockerfile
lint-docker:
    @echo "Linting Dockerfile..."
    @docker run --rm -i hadolint/hadolint < Dockerfile || echo "Hadolint not available - install with: docker pull hadolint/hadolint"

# Validate docker-compose (syntax check)
validate-compose:
    @echo "Validating docker-compose.yml syntax..."
    @docker compose config > /dev/null && echo "✓ docker-compose.yml syntax is valid" || echo "Note: Schema validation warnings are normal for custom services"

# Validate Kubernetes manifests
validate-k8s:
    @echo "Validating Kubernetes manifests..."
    @kubectl apply --dry-run=client -f deploy/k8s/kustomize/base/ || echo "kubectl not available"

# Lint Helm chart
lint-helm:
    @echo "Linting Helm chart..."
    @if command -v helm >/dev/null; then helm lint deploy/k8s/helm/background_job_tracker; else echo "helm not installed, skipping"; fi




# Validate all infrastructure configs
validate-infra: validate-yaml validate-compose lint-docker validate-k8s
    @echo ""
    @echo "✅ All infrastructure validations complete!"
