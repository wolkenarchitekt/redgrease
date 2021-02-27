import os
from pathlib import Path

import pytest

from redgrease.client import RedisGears, safe_str

scripts_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "gear_scripts")


def gear_script(file):
    return os.path.join(scripts_dir, file)


def gear_scripts(file_pattern):
    directory = Path(str(scripts_dir))
    return directory.rglob(file_pattern)


def read(file_pattern):
    directory = Path(str(scripts_dir))
    files_contents = []
    for file_path in directory.rglob(file_pattern):
        with open(file_path, "r") as file:
            files_contents.append((file_path.name, file.read()))
    return files_contents


@pytest.mark.parametrize(
    "script", read("redgrease_runtime_redis_api_*.py"), ids=lambda x: x[0][-10:]
)
def test_basic(rg: RedisGears, script):
    script_name, script_contents = script
    # First set no keys
    res_0 = rg.gears.pyexecute(script_contents)
    assert res_0 is not None
    assert res_0 == []

    orig_val = 13
    key = "NUM"

    assert rg.set(key, orig_val)

    res_1 = rg.gears.pyexecute(script_contents)
    assert res_1 is not None
    assert res_1
    assert res_1.errors == []

    assert float(safe_str(rg.get(key))) == orig_val * 2
