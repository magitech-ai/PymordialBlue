"""Tests for BluestacksController."""

from unittest.mock import MagicMock, patch

from pymordial.core.blueprints.emulator_device import EmulatorState

from pymordialblue.android_app import AndroidApp
from pymordialblue.bluestacks_controller import BluestacksController


def test_controller_init(mock_config):
    """Test controller initialization and plugin resolution."""
    with patch("pymordialblue.utils.configs.get_config", return_value=mock_config):
        controller = BluestacksController()
        assert controller.adb is not None
        assert controller.ui is not None
        assert controller.bluestacks is not None


def test_controller_open_app(mock_controller, mock_config):
    """Test open_app delegation."""
    app = AndroidApp(app_name="TestApp", package_name="com.test.app")
    mock_controller.adb.open_app = MagicMock(return_value=True)

    assert mock_controller.open_app(app) is True

    call_args = mock_controller.adb.open_app.call_args[1]
    assert call_args["app_name"] == "TestApp"
    assert call_args["package_name"] == "com.test.app"


def test_controller_click_element(mock_controller):
    """Test click_element delegation."""
    from pymordial.ui.image import PymordialImage

    with patch("pathlib.Path.exists", return_value=True):
        element = PymordialImage(label="test_el", filepath="fake.png", confidence=0.9)

    mock_controller.bluestacks.state.current_state = EmulatorState.READY
    mock_controller.adb.is_connected = MagicMock(return_value=True)
    mock_controller.adb.run_command = MagicMock()

    # Mock find_element behavior
    with patch.object(mock_controller, "find_element", return_value=(100, 200)):
        assert mock_controller.click_element(element) is True
        # click_element calls click_coord which calls adb.run_command(tap_command)
        assert mock_controller.adb.run_command.called


def test_controller_capture_screen(mock_controller):
    """Test capture_screen delegation."""
    mock_controller.adb.capture_screen = MagicMock(return_value=b"fake_bytes")
    assert mock_controller.capture_screen() == b"fake_bytes"


def test_controller_disconnect(mock_controller):
    """Test disconnect delegation."""
    mock_controller.adb.is_connected = MagicMock(return_value=True)
    mock_controller.adb.disconnect = MagicMock()
    mock_controller.disconnect()
    assert mock_controller.adb.disconnect.called


class FakeAdbPlugin:
    """A third-party adb override: a different class than built-in AdbDevice."""

    name = "adb"
    version = "9.9.9"
    host = "9.9.9.9"
    port = 5555

    def initialize(self, config=None):
        pass

    def shutdown(self):
        pass


def test_controller_uses_passed_adb_host(mock_config):
    """The adb_host passed to the controller must win over entry points.

    The packages declare their own device classes as entry points, so the
    registry holds a default-constructed AdbDevice (127.0.0.1). Taking it
    at face value silently ignored the address the caller passed in.
    """
    with patch("pymordialblue.utils.configs.get_config", return_value=mock_config):
        controller = BluestacksController(adb_host="10.0.0.9", adb_port=5555)
        assert controller.adb.host == "10.0.0.9"
        assert controller.adb.port == 5555
        assert controller.registry.get("adb") is controller.adb


def test_controller_defaults_adb_host_from_config(mock_config):
    """With no entry points loaded, host/port come from the config defaults.

    Before the fix the default factory built AdbDevice(None, None), which
    can never connect; the entry-point default used to hide that.
    """
    from pymordial.core.registry import PluginRegistry

    with (
        patch("pymordialblue.utils.configs.get_config", return_value=mock_config),
        patch.object(PluginRegistry, "load_from_entry_points", lambda self: None),
    ):
        controller = BluestacksController()
        assert controller.adb.host == "127.0.0.1"
        assert controller.adb.port == 5555


def test_controller_still_uses_genuine_override_plugin(mock_config):
    """A registered plugin of a different class must still win."""
    from pymordial.core.registry import PluginRegistry

    fake = FakeAdbPlugin()

    def _load_override(self):
        self.register(fake)

    with (
        patch("pymordialblue.utils.configs.get_config", return_value=mock_config),
        patch.object(PluginRegistry, "load_from_entry_points", _load_override),
    ):
        controller = BluestacksController()
        assert controller.adb is fake
        assert controller.adb.host == "9.9.9.9"
