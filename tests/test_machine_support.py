from vice_next_mcp.process import SUPPORTED


def test_keyboard_machine_executables_are_supported():
    assert SUPPORTED == {
        "c64": "x64sc",
        "c64-fast": "x64",
        "c128": "x128",
        "vic20": "xvic",
        "plus4": "xplus4",
        "c16": "xplus4",
        "pet": "xpet",
        "cbm2": "xcbm2",
        "cbm5x0": "xcbm5x0",
        "c64dtv": "x64dtv",
        "scpu64": "xscpu64",
    }
