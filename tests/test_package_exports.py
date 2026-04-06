from ipilot import iPilot


def test_i_pilot_exports_new_name_only():
    assert iPilot.__name__ == "iPilot"
