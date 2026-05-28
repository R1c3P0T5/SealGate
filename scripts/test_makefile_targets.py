import subprocess


def make_dry_run(target: str) -> str:
    result = subprocess.run(
        ["make", "-n", target],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_production_targets_use_base_compose_file() -> None:
    for target in ("prod", "server", "worker", "update"):
        command = make_dry_run(target)

        assert "-f docker-compose.yml" in command


def test_update_pulls_full_production_stack_and_recreates_containers() -> None:
    command = make_dry_run("update")

    assert "--profile full pull" in command
    assert "--profile full up -d --force-recreate" in command
