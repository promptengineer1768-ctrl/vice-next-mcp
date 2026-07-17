"""Run coroutine tests without adding a runtime test-plugin dependency."""
import asyncio
import inspect

def pytest_pyfunc_call(pyfuncitem):
    function=pyfuncitem.obj
    if not inspect.iscoroutinefunction(function): return None
    kwargs={name:pyfuncitem.funcargs[name] for name in pyfuncitem._fixtureinfo.argnames}
    asyncio.run(function(**kwargs))
    return True
