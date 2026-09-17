"""Structural validation of docker-compose.yml.

Docker itself was not available in the environment these files were built
in (see README.md), so these tests do not spin up containers. Instead they
parse the compose file with PyYAML and assert that its structure is
internally consistent: every service that's referenced actually exists,
every build context points at a real directory, every named volume that's
mounted is declared, etc. This catches typos and dangling references, but
it is not a substitute for `docker compose up --build`.
"""
import os

import yaml

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE_PATH = os.path.join(REPO_ROOT, "docker-compose.yml")

EXPECTED_SERVICES = {"users-service", "orders-service", "api-gateway-service"}


def load_compose():
    with open(COMPOSE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_compose_file_is_valid_yaml_with_services():
    compose = load_compose()
    assert isinstance(compose, dict)
    assert "services" in compose
    assert isinstance(compose["services"], dict)


def test_compose_declares_exactly_the_expected_services():
    compose = load_compose()
    assert set(compose["services"].keys()) == EXPECTED_SERVICES


def test_every_build_context_exists_on_disk():
    compose = load_compose()
    for name, service in compose["services"].items():
        build = service.get("build")
        assert build is not None, f"service {name} has no build context"
        context = build["context"] if isinstance(build, dict) else build
        context_path = os.path.join(REPO_ROOT, context)
        assert os.path.isdir(context_path), f"build context for {name} missing: {context_path}"
        dockerfile_name = build.get("dockerfile", "Dockerfile") if isinstance(build, dict) else "Dockerfile"
        assert os.path.isfile(os.path.join(context_path, dockerfile_name)), (
            f"Dockerfile missing for service {name}"
        )


def test_every_depends_on_reference_exists():
    compose = load_compose()
    services = compose["services"]
    for name, service in services.items():
        for dep in service.get("depends_on", []):
            assert dep in services, f"service {name} depends_on unknown service {dep}"


def test_every_mounted_named_volume_is_declared():
    compose = load_compose()
    declared_volumes = set((compose.get("volumes") or {}).keys())
    for name, service in compose["services"].items():
        for mount in service.get("volumes", []):
            vol_name = mount.split(":", 1)[0]
            # Skip bind mounts (paths), only check named volumes.
            if vol_name.startswith(".") or vol_name.startswith("/"):
                continue
            assert vol_name in declared_volumes, (
                f"service {name} mounts undeclared volume {vol_name}"
            )


def test_every_service_is_attached_to_a_declared_network():
    compose = load_compose()
    declared_networks = set((compose.get("networks") or {}).keys())
    assert declared_networks, "no top-level networks declared"
    for name, service in compose["services"].items():
        service_networks = service.get("networks", [])
        assert service_networks, f"service {name} is not attached to any network"
        for net in service_networks:
            assert net in declared_networks, f"service {name} uses undeclared network {net}"


def test_orders_and_gateway_have_users_service_url_env_var():
    compose = load_compose()
    for name in ("orders-service", "api-gateway-service"):
        env = compose["services"][name].get("environment", [])
        joined = "\n".join(env) if isinstance(env, list) else str(env)
        assert "USERS_SERVICE_URL" in joined, f"{name} is missing USERS_SERVICE_URL"


def test_gateway_has_orders_service_url_env_var():
    compose = load_compose()
    env = compose["services"]["api-gateway-service"].get("environment", [])
    joined = "\n".join(env) if isinstance(env, list) else str(env)
    assert "ORDERS_SERVICE_URL" in joined


def test_gateway_depends_on_both_backend_services():
    compose = load_compose()
    deps = set(compose["services"]["api-gateway-service"].get("depends_on", []))
    assert deps == {"users-service", "orders-service"}
