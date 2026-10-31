import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vela import mangohud, runtime


class BackgroundTests(unittest.TestCase):
    def test_blur_roundtrip_and_disable(self):
        base = 'position=top-right\nbackground_alpha=0.4\n'
        content = mangohud.managed_content(base, 60, 'early', True, {'vela_background_blur': 12})
        self.assertEqual(mangohud.appearance_values(content)['vela_background_blur'], 12)
        self.assertTrue(content.startswith(base))
        self.assertEqual(content, mangohud.managed_content(content, 60, 'early', True, {'vela_background_blur': 12}))
        off = mangohud.managed_content(content, 60, 'early', True, {'vela_background_blur': 0})
        self.assertEqual(mangohud.appearance_values(off)['vela_background_blur'], 0)
        default = mangohud.managed_content('', 0, 'early', True, {'vela_background_blur': 0})
        self.assertNotIn('vela_background_blur', default)
        for value in (-1, 33, float('nan'), float('inf'), '12'):
            with self.subTest(value=value), self.assertRaises(mangohud.ControlError):
                mangohud.managed_content('', 0, 'early', True, {'vela_background_blur': value})

    def test_padding_roundtrip_and_validation(self):
        base = 'position=top-right\nwidth=360\ncustom=1\n'
        content = mangohud.managed_content(base, 60, 'early', True, {'vela_padding': 24})
        self.assertEqual(mangohud.appearance_values(content)['vela_padding'], 24)
        self.assertTrue(content.startswith(base))
        self.assertEqual(content, mangohud.managed_content(content, 60, 'early', True, {'vela_padding': 24}))
        zero = mangohud.managed_content(content, 60, 'early', True, {'vela_padding': 0})
        self.assertEqual(mangohud.appearance_values(zero)['vela_padding'], 0)
        self.assertIn('vela_padding=0', zero)
        default = mangohud.managed_content('', 0, 'early', True, {'vela_padding': 5})
        self.assertNotIn('vela_padding', default)
        for value in (-1, 65, float('nan'), float('inf'), '12'):
            with self.subTest(value=value), self.assertRaises(mangohud.ControlError):
                mangohud.managed_content('', 0, 'early', True, {'vela_padding': value})

    def test_appearance_preserves_explicit_position(self):
        base = 'position=bottom-right\noffset_x=25\noffset_y=40\nhud_no_margin\n'
        content = mangohud.managed_content(base, 60, 'early', True,
                    {'vela_shadow_alpha': .7, 'vela_shadow_blur': 40,
                     'vela_shadow_offset_x': -30, 'text_color': 'FFFFFF'})
        self.assertTrue(content.startswith(base))

    def test_roundtrip_and_disable(self):
        options = {'vela_background_noise': .12, 'vela_shadow_alpha': .5}
        content = mangohud.managed_content('unrelated=1\n', 60, 'early', True, options)
        self.assertEqual(mangohud.appearance_values(content)['vela_background_noise'], .12)
        self.assertEqual(mangohud.appearance_values(content)['vela_shadow_alpha'], .5)
        self.assertEqual(content, mangohud.managed_content(content, 60, 'early', True, options))
        disabled = mangohud.managed_content(content, 60, 'early', True,
                                           dict.fromkeys(options, 0))
        self.assertEqual(mangohud.appearance_values(disabled)['vela_background_noise'], 0)
        self.assertEqual(mangohud.appearance_values(disabled)['vela_shadow_alpha'], 0)
        self.assertIn('unrelated=1', disabled)

    def test_stock_defaults_have_no_custom_keys(self):
        content = mangohud.managed_content('', 0, 'early', True,
                    {'vela_background_noise': 0, 'vela_shadow_alpha': 0})
        self.assertNotIn('vela_background_', content)

    def test_border_roundtrip_and_defaults(self):
        options = {'vela_border_color': '4187eb', 'vela_border_width': 1.5, 'vela_border_alpha': .35}
        content = mangohud.managed_content('custom=1\n', 45, 'late', True, options)
        self.assertEqual(mangohud.color_values(content)['vela_border_color'], '4187EB')
        self.assertEqual(mangohud.appearance_values(content)['vela_border_width'], 1.5)
        self.assertEqual(mangohud.appearance_values(content)['vela_border_alpha'], .35)
        self.assertEqual(content, mangohud.managed_content(content, 45, 'late', True, options))
        disabled = mangohud.managed_content(content, 45, 'late', True, {'vela_border_width': 0})
        self.assertEqual(mangohud.appearance_values(disabled)['vela_border_width'], 0)
        self.assertEqual(mangohud.color_values(disabled)['vela_border_color'], '4187EB')
        default = mangohud.managed_content('', 0, 'early', True,
            {'vela_border_width': 0, 'vela_border_alpha': 1, 'vela_border_color': '414141'})
        self.assertNotIn('vela_border_', default)

    def test_invalid_border_values(self):
        for key, value in (('vela_border_width', -1), ('vela_border_width', 9),
                           ('vela_border_alpha', 1.1), ('vela_border_width', float('nan')),
                           ('vela_border_color', 'invalid'), ('vela_border_color', 'FFFFFF\nfps_limit=0')):
            with self.subTest(key=key, value=value), self.assertRaises(mangohud.ControlError):
                mangohud.managed_content('', 0, 'early', True, {key: value})

    def test_invalid_effects_rejected(self):
        for value in (-1, 1.1, float('nan'), float('inf'), '0.1'):
            with self.subTest(value=value), self.assertRaises(mangohud.ControlError):
                mangohud.managed_content('', 0, 'early', True, {'vela_background_noise': value})

    def test_save_preserves_limiter_inode_and_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'game.conf'
            path.write_text('fps_limit=45\ncustom_option=1\n')
            inode = path.stat().st_ino
            mangohud.save_appearance(path, {'vela_background_noise': .08, 'vela_shadow_alpha': .5})
            content = path.read_text()
            self.assertEqual(path.stat().st_ino, inode)
            self.assertEqual(mangohud.values_from_content(content)[0], 45)
            self.assertIn('custom_option=1', content)
            self.assertEqual(mangohud.appearance_values(content)['vela_shadow_alpha'], .5)

    def test_shadow_roundtrip_and_retired_frost(self):
        options = {'vela_shadow_alpha': .6, 'vela_shadow_blur': 24,
                   'vela_shadow_offset_x': -12, 'vela_shadow_offset_y': 8,
                   'vela_shadow_color': '4187eb', 'vela_background_frost': 1}
        content = mangohud.managed_content('vela_background_frost=1\nkeep=1\n', 60, 'early', True, options)
        self.assertNotIn('vela_background_frost', content)
        self.assertIn('keep=1', content)
        values = mangohud.appearance_values(content)
        self.assertEqual(values['vela_shadow_offset_x'], -12)
        self.assertEqual(values['vela_shadow_blur'], 24)
        self.assertEqual(mangohud.color_values(content)['vela_shadow_color'], '4187EB')
        self.assertEqual(content, mangohud.managed_content(content, 60, 'early', True, options))
        for key, value in (('vela_shadow_alpha', 1.1), ('vela_shadow_blur', -1),
                           ('vela_shadow_blur', 41), ('vela_shadow_offset_x', -41),
                           ('vela_shadow_offset_y', float('nan')), ('vela_shadow_color', 'oops')):
            with self.subTest(key=key, value=value), self.assertRaises(mangohud.ControlError):
                mangohud.managed_content('', 0, 'early', True, {key: value})
        defaults = mangohud.managed_content('', 0, 'early', True,
            {'vela_shadow_alpha': 0, 'vela_shadow_blur': 16, 'vela_shadow_offset_x': 0,
             'vela_shadow_offset_y': 4, 'vela_shadow_color': '000000'})
        self.assertNotIn('vela_shadow_', defaults)

    def test_launcher_preserves_other_layers_and_environment(self):
        base = {'VK_INSTANCE_LAYERS': 'VK_LAYER_OTHER:VK_LAYER_MANGOHUD_overlay_x86_64',
                'VK_ADD_LAYER_PATH': '/other/layers', 'LD_PRELOAD': '/other.so:/old/libMangoHud_shim.so'}
        with tempfile.TemporaryDirectory() as directory, patch.object(runtime, 'available', return_value=True):
            env = runtime.environment(directory, base)
            manifest = json.loads((Path(directory) / 'Vela-MangoHud.json').read_text())
            self.assertEqual(env['DISABLE_MANGOHUD'], '1')
            self.assertIn('VK_LAYER_OTHER', env['VK_INSTANCE_LAYERS'])
            self.assertNotIn(':VK_LAYER_MANGOHUD_overlay_', env['VK_INSTANCE_LAYERS'])
            self.assertIn('/other.so', env['LD_PRELOAD'])
            self.assertNotIn('/old/', env['LD_PRELOAD'])
            self.assertEqual(manifest['layer']['name'], env['VK_INSTANCE_LAYERS'].split(':')[-1])
            self.assertTrue(env['VK_ADD_LAYER_PATH'].endswith(':/other/layers'))
            self.assertNotIn('DISABLE_MANGOHUD', base)


if __name__ == '__main__':
    unittest.main()
