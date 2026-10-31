"""Contracts for catalog parsing, desktop downloads and package licenses."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse
from vela.google_fonts import FontFamily, parse_catalog, parse_ttf_url, package_licenses, css_url


class GoogleFontsContracts(unittest.TestCase):
    def test_catalog_handles_site_prefix_and_extreme_weights(self):
        data = {'familyMetadataList': [{'family':'Example','category':'Sans Serif','fonts':{'1':{},'400':{},'1000i':{},'invalid':{}}}]}
        families = parse_catalog(b")]}'\n" + json.dumps(data).encode())
        self.assertEqual(families[0].variants, ('1','400','1000i'))
        self.assertEqual(families[0].category, 'Sans serif')
        with self.assertRaises(ValueError): parse_catalog(b'{"changedSchema":[]}')

    def test_desktop_css_request_preserves_italic_weight_and_subset(self):
        family = FontFamily('JetBrains Mono','Monospace',('700i',))
        query = parse_qs(urlparse(css_url(family,'700i',True)).query)
        self.assertEqual(query['family'],['JetBrains Mono:ital,wght@1,700'])
        self.assertIn('text',query)
        self.assertNotIn('text',parse_qs(urlparse(css_url(family,'700i')).query))

    def test_reject_split_fonts_and_non_google_sources(self):
        valid = b'@font-face {src: url(https://fonts.gstatic.com/example.ttf)}'
        self.assertEqual(parse_ttf_url(valid),'https://fonts.gstatic.com/example.ttf')
        for invalid in (b'url(https://example.com/font.ttf)', valid+b'url(https://fonts.gstatic.com/other.ttf)', b'<html>Error</html>'):
            with self.assertRaises(ValueError): parse_ttf_url(invalid)

    def test_package_keeps_license_without_using_manifest_paths(self):
        body = {'manifest':{'files':[{'filename':'../../OFL.txt','contents':'Open Font License\n'*20},{'filename':'README.txt','contents':'readme'}]}}
        self.assertEqual(list(package_licenses(json.dumps(body).encode())),['OFL.txt'])
        with self.assertRaises(ValueError):package_licenses(b'{"manifest":{"files":[]}}')

    def test_existing_presets_remain_available(self):
        with tempfile.TemporaryDirectory() as directory, patch('vela.google_fonts.font_directory',return_value=Path(directory)):
            old = Path(directory)/'jetbrains-mono/jetbrains-mono-Bold.ttf';old.parent.mkdir();old.write_bytes(b'font')
            family = FontFamily('JetBrains Mono','Monospace',('700','700i'))
            self.assertEqual(family.path('700'),old)
            self.assertNotEqual(family.path('700i'),old)

    def test_bundled_catalog_covers_google_fonts_categories(self):
        path = Path(__file__).resolve().parents[1]/'vela/assets/google-fonts.json'
        families = parse_catalog(path.read_bytes())
        self.assertGreater(len(families),1900)
        self.assertEqual({f.category for f in families},{'Monospace','Sans serif','Serif','Display','Handwriting'})


if __name__=='__main__':unittest.main()
