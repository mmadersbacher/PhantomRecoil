import unittest
from unittest import mock

from macro import RecoilMacro, get_pointer_speed, get_enhance_pointer_precision, POINTER_SPEED_DEFAULT
import win32con


class TestRecoilMacroValidation(unittest.TestCase):
    def setUp(self):
        self.macro = RecoilMacro()

    def test_update_recoil_sanitizes_non_numeric(self):
        self.macro.update_recoil('abc', None)
        self.assertEqual(self.macro.recoil_x, 0.0)
        self.assertEqual(self.macro.recoil_y, 0.0)

    def test_set_multiplier_clamps_bounds(self):
        self.macro.set_multiplier(-10)
        self.assertEqual(self.macro.multiplier, 0.01)

        self.macro.set_multiplier(42)
        self.assertEqual(self.macro.multiplier, 1.0)

    def test_set_multiplier_fallback_default(self):
        self.macro.set_multiplier('nan-value')
        self.assertEqual(self.macro.multiplier, 0.5)

    def test_set_hotkey_accepts_capslock(self):
        result = self.macro.set_hotkey(win32con.VK_CAPITAL)  # 0x14
        self.assertTrue(result)
        self.assertEqual(self.macro.hotkey_vk, win32con.VK_CAPITAL)

    def test_set_hotkey_accepts_function_keys(self):
        for vk in [0x70, 0x71, 0x7B]:  # F1, F2, F12
            result = self.macro.set_hotkey(vk)
            self.assertTrue(result, f"set_hotkey should accept VK 0x{vk:02X}")
            self.assertEqual(self.macro.hotkey_vk, vk)

    def test_set_hotkey_rejects_letter_key(self):
        self.macro.set_hotkey(win32con.VK_CAPITAL)  # set a known good key first
        result = self.macro.set_hotkey(0x41)         # 'A' — not allowed
        self.assertFalse(result)
        self.assertEqual(self.macro.hotkey_vk, win32con.VK_CAPITAL)  # unchanged

    def test_set_hotkey_rejects_enter(self):
        result = self.macro.set_hotkey(0x0D)  # VK_RETURN
        self.assertFalse(result)

    def test_get_state_snapshot_includes_hotkey(self):
        self.macro.set_hotkey(0x72)  # F3
        snapshot = self.macro.get_state_snapshot()
        self.assertIn('hotkey_vk', snapshot)
        self.assertIn('hotkey_name', snapshot)
        self.assertIn('game_running', snapshot)
        self.assertEqual(snapshot['hotkey_vk'], 0x72)
        self.assertEqual(snapshot['hotkey_name'], 'F3')


class TestSendInput(unittest.TestCase):
    def test_send_relative_mouse_move_calls_sendinput(self):
        """SendInput should be invoked with one event of type INPUT_MOUSE."""
        import macro as _macro
        with mock.patch.object(_macro.ctypes.windll.user32, 'SendInput') as mock_send:
            _macro._send_relative_mouse_move(3, 5)
            self.assertTrue(mock_send.called)
            call_args = mock_send.call_args
            # First arg is count=1
            self.assertEqual(call_args[0][0], 1)

    def test_send_relative_mouse_move_zero_is_valid(self):
        """Zero-delta move should still call SendInput without raising."""
        import macro as _macro
        with mock.patch.object(_macro.ctypes.windll.user32, 'SendInput'):
            _macro._send_relative_mouse_move(0, 0)  # must not raise


class TestRapidFire(unittest.TestCase):
    def setUp(self):
        self.macro = RecoilMacro()

    def test_set_rapid_fire_false_releases_and_resets_cycle(self):
        import macro as _macro

        self.macro._rf_btn_down = True
        self.macro._rf_hold_neutralized = True

        with mock.patch.object(_macro, '_send_mouse_button') as mock_button:
            self.macro.set_rapid_fire(False)

        mock_button.assert_called_once_with(_macro._MOUSEEVENTF_LEFTUP)
        self.assertFalse(self.macro._rf_btn_down)
        self.assertFalse(self.macro._rf_hold_neutralized)

    def test_mouse_hook_ignores_injected_clicks(self):
        import macro as _macro

        self.macro._handle_mouse_hook_event(_macro._WM_LBUTTONDOWN, _macro._LLMHF_INJECTED)
        self.assertFalse(self.macro._physical_lmb_pressed)

        self.macro._handle_mouse_hook_event(_macro._WM_LBUTTONDOWN, 0)
        self.assertTrue(self.macro._physical_lmb_pressed)

        self.macro._handle_mouse_hook_event(_macro._WM_LBUTTONUP, 0)
        self.assertFalse(self.macro._physical_lmb_pressed)

    def test_rf_fire_shot_finishes_with_leftup(self):
        import macro as _macro

        with (
            mock.patch.object(_macro, '_send_button_with_move') as mock_button_with_move,
            mock.patch.object(_macro.time, 'sleep'),
        ):
            self.macro._rf_fire_shot(recoil_x=2, recoil_y=3, multiplier=1.0)

        # Must call _send_button_with_move exactly twice: DOWN then UP
        self.assertEqual(mock_button_with_move.call_count, 2)
        self.assertEqual(mock_button_with_move.call_args_list[0][0][0], _macro._MOUSEEVENTF_LEFTDOWN)
        self.assertEqual(mock_button_with_move.call_args_list[1][0][0], _macro._MOUSEEVENTF_LEFTUP)
        self.assertFalse(self.macro._rf_btn_down)
        self.assertEqual(self.macro.accumulated_x, 0.0)
        self.assertEqual(self.macro.accumulated_y, 0.0)

    def test_rf_fire_shot_down_before_up(self):
        """DOWN event must always precede the matching UP in a single shot."""
        import macro as _macro

        order = []
        def track(flags, dx=0, dy=0):
            order.append(flags)

        with (
            mock.patch.object(_macro, '_send_button_with_move', side_effect=track),
            mock.patch.object(_macro.time, 'sleep'),
        ):
            self.macro._rf_fire_shot(recoil_x=0, recoil_y=0, multiplier=1.0)

        self.assertIn(_macro._MOUSEEVENTF_LEFTDOWN, order)
        self.assertIn(_macro._MOUSEEVENTF_LEFTUP, order)
        self.assertLess(order.index(_macro._MOUSEEVENTF_LEFTDOWN), order.index(_macro._MOUSEEVENTF_LEFTUP))

    def test_rf_fire_shot_releases_on_exception(self):
        """If an exception occurs after DOWN, LEFTUP must still be sent via _rf_release."""
        import macro as _macro

        # time.sleep raises immediately → interrupts after DOWN was injected
        with (
            mock.patch.object(_macro, '_send_button_with_move'),
            mock.patch.object(_macro, '_send_mouse_button') as mock_btn,
            mock.patch.object(_macro.time, 'sleep', side_effect=RuntimeError("interrupted")),
        ):
            with self.assertRaises(RuntimeError):
                self.macro._rf_fire_shot(recoil_x=2, recoil_y=3, multiplier=1.0)

        mock_btn.assert_called_once_with(_macro._MOUSEEVENTF_LEFTUP)
        self.assertFalse(self.macro._rf_btn_down)


class TestSystemInfo(unittest.TestCase):
    def test_get_pointer_speed_returns_int_in_range(self):
        speed = get_pointer_speed()
        self.assertIsInstance(speed, int)
        self.assertGreaterEqual(speed, 1)
        self.assertLessEqual(speed, 20)

    def test_get_pointer_speed_fallback_on_api_error(self):
        import macro as _macro
        with mock.patch.object(_macro.ctypes.windll.user32, 'SystemParametersInfoW', side_effect=OSError):
            speed = get_pointer_speed()
        self.assertEqual(speed, POINTER_SPEED_DEFAULT)

    def test_get_enhance_pointer_precision_returns_bool(self):
        result = get_enhance_pointer_precision()
        self.assertIsInstance(result, bool)

    def test_get_enhance_pointer_precision_fallback_on_api_error(self):
        import macro as _macro
        with mock.patch.object(_macro.ctypes.windll.user32, 'SystemParametersInfoW', side_effect=OSError):
            result = get_enhance_pointer_precision()
        self.assertFalse(result)

    def test_pointer_speed_default_constant(self):
        self.assertEqual(POINTER_SPEED_DEFAULT, 10)


if __name__ == '__main__':
    unittest.main()
