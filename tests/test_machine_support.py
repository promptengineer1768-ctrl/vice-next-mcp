from vice_next_mcp.process import SUPPORTED


def test_keyboard_machine_executables_are_supported():
    assert SUPPORTED == {
        "c64": "x64sc",
        "c128": "x128",
        "vic20": "xvic",
        "plus4": "xplus4",
        "c16": "xplus4",
        "pet": "xpet",
    }
