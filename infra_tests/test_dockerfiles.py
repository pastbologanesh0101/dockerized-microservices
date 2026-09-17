"""Structural (grep-style) validation of each service's Dockerfile.

These checks confirm basic Dockerfile correctness -- starts with FROM, has
an EXPOSE and a CMD, installs from requirements.txt, etc. -- without
actually building an image, since no Docker daemon is available here.
"""
import os
import re

import pytest
import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SERVICE_PORTS = {
    "users-service": "5001",
    "orders-service": "5002",
    "api-gateway-service": "5000",
}


def read_dockerfile(service_name):
    path = os.path.join(REPO_ROOT, service_name, "Dockerfile")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.mark.parametrize("service_name", sorted(SERVICE_PORTS.keys()))
def test_dockerfile_exists(service_name):
    path = os.path.join(REPO_ROOT, service_name, "Dockerfile")
    assert os.path.isfile(path)


@pytest.mark.parametrize("service_name", sorted(SERVICE_PORTS.keys()))
def test_dockerfile_starts_with_from(service_name):
    content = read_dockerfile(service_name)
    non_comment_lines = [
        line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")
    ]
    assert non_comment_lines, f"{service_name} Dockerfile is empty"
    assert non_comment_lines[0].upper().startswith("FROM"), (
        f"{service_name} Dockerfile must start with FROM"
    )


@pytest.mark.parametrize("service_name", sorted(SERVICE_PORTS.keys()))
def test_dockerfile_uses_a_python_slim_base_image(service_name):
    content = read_dockerfile(service_name)
    match = re.search(r"^FROM\s+(\S+)", content, re.MULTILINE)
    assert match, f"{service_name} Dockerfile has no FROM instruction"
    assert "python" in match.group(1).lower()


@pytest.mark.parametrize("service_name", sorted(SERVICE_PORTS.keys()))
def test_dockerfile_installs_requirements(service_name):
    content = read_dockerfile(service_name)
    assert "requirements.txt" in content
    assert re.search(r"pip install", content)


@pytest.mark.parametrize("service_name, expected_port", sorted(SERVICE_PORTS.items()))
def test_dockerfile_exposes_correct_port(service_name, expected_port):
    content = read_dockerfile(service_name)
    match = re.search(r"^EXPOSE\s+(\d+)", content, re.MULTILINE)
    assert match, f"{service_name} Dockerfile has no EXPOSE instruction"
    assert match.group(1) == expected_port


@pytest.mark.parametrize("service_name, expected_port", sorted(SERVICE_PORTS.items()))
def test_dockerfile_cmd_binds_matching_port(service_name, expected_port):
    content = read_dockerfile(service_name)
    match = re.search(r"^CMD\s+(.+)$", content, re.MULTILINE)
    assert match, f"{service_name} Dockerfile has no CMD instruction"
    assert expected_port in match.group(1)
    assert "gunicorn" in match.group(1)
    assert "wsgi:app" in match.group(1)


@pytest.mark.parametrize("service_name, expected_port", sorted(SERVICE_PORTS.items()))
def test_compose_port_mapping_matches_dockerfile_expose(service_name, expected_port):
    with open(os.path.join(REPO_ROOT, "docker-compose.yml"), "r", encoding="utf-8") as f:
        compose = yaml.safe_load(f)
    ports = compose["services"][service_name].get("ports", [])
    assert any(p.endswith(f":{expected_port}") for p in ports), (
        f"docker-compose.yml port mapping for {service_name} doesn't match Dockerfile EXPOSE {expected_port}"
    )
