import time
from typing import List

import pytest

import redgrease
import redgrease.client
import redgrease.data
from redgrease.client import RedisGears
from redgrease.utils import safe_str, str_if_bytes

# Other things to test:
# - Syntactinc sugar / enums
# - cli / loader


@pytest.mark.parametrize("package", ["numpy"])
def test_pydumpreqs(rg: RedisGears, package):
    orig_reqs = rg.gears.pydumpreqs()
    assert isinstance(orig_reqs, list)

    preexisting = []
    for req in orig_reqs:
        assert req
        assert isinstance(req, redgrease.client.PyRequirementInfo)
        assert req.GearReqVersion
        assert isinstance(req.GearReqVersion, int)
        assert req.Name
        assert isinstance(req.Name, str)
        preexisting.append(req.Name)
        assert req.IsDownloaded
        assert isinstance(req.IsDownloaded, bool)
        assert req.IsInstalled
        assert isinstance(req.IsInstalled, bool)
        assert req.Wheels
        assert isinstance(req.Wheels, list)

    if package not in preexisting:
        # Add a requirement for package
        assert rg.gears.pyexecute("", requirements=[package])

        new_reqs = rg.gears.pydumpreqs()

        assert any(r.Name == package for r in new_reqs)


@pytest.mark.parametrize(
    "arg_list",
    [[], ["Olufsen"], ["bang", "bang!"], [4, "the", "buck"]],
    ids=lambda x: f"{len(x)}arg",
)
@pytest.mark.parametrize("mode", ["blocking", "unblocking"])
def test_trigger(rg: RedisGears, arg_list: List, mode: str):
    triggger_name = "Bang"
    unblocking: bool = mode == "unblocking"
    fun_str = (
        """GB('CommandReader')"""
        """.flatmap(lambda x: x)."""
        f"""register(trigger='{triggger_name}')"""
    )
    assert rg.gears.pyexecute(fun_str, unblocking=unblocking)
    res = rg.gears.trigger(triggger_name, *arg_list)
    assert isinstance(res, redgrease.data.Execution)
    assert isinstance(res.result, list)
    assert len(res) == len(arg_list) + 1
    # For some reason flatmap seems to reverse the order
    str_res = list(map(safe_str, res))
    for arg in arg_list:
        assert str(arg) in str_res


@pytest.mark.parametrize("mode", ["blocking", "unblocking"])
def test_dumpregistrations(rg: RedisGears, mode: str):
    triggger_name = "Bang"
    unblocking: bool = mode == "unblocking"
    fun_str = (
        """GB('CommandReader')"""
        """.flatmap(lambda x: x)."""
        f"""register(trigger='{triggger_name}')"""
    )
    assert rg.gears.pyexecute(fun_str, unblocking=unblocking)
    registrations_list = rg.gears.dumpregistrations()
    assert registrations_list
    assert isinstance(registrations_list, list)
    assert len(registrations_list) == 1
    reg = registrations_list[0]
    assert reg
    assert isinstance(reg, redgrease.data.Registration)
    assert reg.id
    assert isinstance(reg.id, redgrease.data.ExecID)
    assert reg.reader
    assert isinstance(
        reg.reader, str
    )  # This should mabe be redgrease.Reader but as enum : Issue #4
    assert reg.desc is None  # Not sure when and how this field isr set

    # # Registration data
    assert reg.RegistrationData
    assert isinstance(reg.RegistrationData, redgrease.data.RegData)
    rdat = reg.RegistrationData
    assert rdat.mode
    assert isinstance(
        rdat.mode, str
    )  # This should maybe le redgrease.TriggerMode, but as enum : Issue #5
    assert rdat.mode == redgrease.TriggerMode.Async
    assert isinstance(rdat.numTriggered, int)
    assert rdat.numTriggered == 0
    assert isinstance(rdat.numSuccess, int)
    assert rdat.numSuccess == 0
    assert isinstance(rdat.numFailures, int)
    assert rdat.numFailures == 0
    assert isinstance(rdat.numAborted, int)
    assert rdat.numAborted == 0
    assert rdat.lastError is None
    assert rdat.args
    assert isinstance(rdat.args, dict)

    # # This is only true for CommandReader registrerd with a trigger
    assert "trigger" in rdat.args
    assert str_if_bytes(rdat.args["trigger"]) == triggger_name

    # # Private Data. Not really impt how it is returned
    # # But want to know if it changes for some reason
    assert reg.PD
    assert isinstance(reg.PD, dict)
    assert "sessionId" in reg.PD.keys()
    assert "depsList" in reg.PD.keys()
    assert isinstance(reg.PD["depsList"], list)
    assert reg.PD["depsList"] == []

    # # Chec that NumTriggered and NumSuccess increase after a trigger
    assert rg.gears.trigger(triggger_name)
    registrations_list_2 = rg.gears.dumpregistrations()
    reg2 = registrations_list_2[0]
    assert reg2.RegistrationData.numTriggered == reg.RegistrationData.numTriggered + 1
    assert reg2.RegistrationData.numSuccess == reg.RegistrationData.numSuccess + 1


def test_unregister(rg: RedisGears):
    triggger_name = "Bang"
    fun_str = (
        """GB('CommandReader')"""
        """.flatmap(lambda x: x)."""
        f"""register(trigger='{triggger_name}')"""
    )
    assert rg.gears.pyexecute(fun_str)
    registrations_list = rg.gears.dumpregistrations()
    exec_id = None
    for reg in registrations_list:
        if (
            "trigger" in reg.RegistrationData.args
            and str_if_bytes(reg.RegistrationData.args["trigger"]) == triggger_name
        ):
            exec_id = reg.id
    assert exec_id
    # TODO: Also test othe "ExecId"-like objects
    assert rg.gears.unregister(exec_id)
    registrations_list_2 = rg.gears.dumpregistrations()
    assert registrations_list_2 == []


@pytest.mark.parametrize("fun_str", ["GB().run()"])
def test_getexecution(rg: RedisGears, fun_str: str):
    # TODO: Test cluster Mode more properly

    exec = rg.gears.pyexecute(fun_str, unblocking=True)
    assert exec
    assert isinstance(exec, redgrease.data.Execution)
    assert exec.result
    assert not exec.errors
    assert isinstance(exec.result, redgrease.data.ExecID)
    shard_id = exec.result.shard_id

    # ! Possibly a race condition that executon is not complete. Ugly AF sln.
    time.sleep(5)

    res = rg.gears.getexecution(exec.result)  # TODO: This is an odd API syntax
    assert res
    assert isinstance(res, dict)
    assert shard_id in res.keys()
    exe_plan = res[exec.result.shard_id]  # TODO: Real awkward
    assert exe_plan
    assert isinstance(exe_plan, redgrease.data.ExecutionPlan)
    assert exe_plan.status
    assert isinstance(exe_plan.status, redgrease.data.ExecutionStatus)
    assert isinstance(exe_plan.shards_received, int)
    assert isinstance(exe_plan.shards_completed, int)
    assert isinstance(exe_plan.results, int)
    assert isinstance(exe_plan.errors, list)
    assert isinstance(exe_plan.total_duration, int)
    assert isinstance(exe_plan.read_duration, int)
    assert isinstance(exe_plan.steps, list)
    assert exe_plan.steps
    for exe_step in exe_plan.steps:
        assert exe_step
        assert isinstance(exe_step, redgrease.data.ExecutionStep)
        assert exe_step.type
        assert isinstance(exe_step.type, str)
        assert isinstance(exe_step.duration, int)
        assert exe_step.name
        assert isinstance(exe_step.name, str)
        assert isinstance(exe_step.arg, str)


# TODO: rethink how execution results should be represented
def test_getresults(rg: RedisGears):
    rg.set("AKEY", 42)
    rg.set("ANOTHERKEY", 1)

    fun_str = """GB().count().run()"""

    exec = rg.gears.pyexecute(fun_str, unblocking=True)
    assert exec is not None
    assert isinstance(exec, redgrease.data.Execution)
    assert exec.result
    assert not exec.errors
    assert isinstance(exec.result, redgrease.data.ExecID)

    # ! Possibly a race condition that executon is not complete. Ugly AF sln.
    time.sleep(5)

    res = rg.gears.getresults(exec.result)  # TODO: is this how we want it to work?
    assert res
    assert isinstance(
        res, list
    )  # TODO: should this not be same as pyexetute returns when bocking?
    assert int(res[0][0]) == 2


@pytest.mark.xfail(reason="Testcase not implemented")
def test_getresultsblocking(rg: RedisGears):
    assert False


@pytest.mark.xfail(reason="Testcase not implemented")
def test_dumpexecutions(rg: RedisGears):
    assert False


@pytest.mark.xfail(reason="Testcase not implemented")
def test_dropexecution(rg: RedisGears):
    assert False


@pytest.mark.xfail(reason="Testcase not implemented")
def test_abortexecution(rg: RedisGears):
    assert False


def test_pystats(rg: RedisGears):
    stats = rg.gears.pystats()
    assert stats
    assert isinstance(stats, redgrease.data.PyStats)

    assert stats.TotalAllocated
    assert isinstance(stats.TotalAllocated, int)
    assert stats.TotalAllocated > 0

    assert stats.PeakAllocated
    assert isinstance(stats.PeakAllocated, int)
    assert stats.PeakAllocated > 0

    assert stats.CurrAllocated
    assert isinstance(stats.CurrAllocated, int)
    assert stats.CurrAllocated > 0


# TODO: Actually test on a cluster setup
@pytest.mark.parametrize("cluster_mode", [False])
def test_infocluster(rg: RedisGears, cluster_mode):
    info = rg.gears.infocluster()
    # Non-c
    if not cluster_mode:
        assert info is None
        return

    assert info


# TODO: Actually test on a cluster setup
def test_refreshcluster(rg: RedisGears):
    # Pretty pointless test, but anyway
    # TODO: Somehow validate that it is run... Unsure of how though
    # TODO: See issue #11
    assert rg.gears.refreshcluster()
