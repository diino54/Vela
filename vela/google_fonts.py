"""Google Fonts catalog, static TTF downloads and small specimen previews."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlparse

from PySide6.QtCore import QObject, Signal, QStandardPaths, QSaveFile, QIODevice, QUrl
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

METADATA_URL = 'https://fonts.google.com/metadata/fonts'
WEIGHTS = {100:'Thin', 200:'ExtraLight', 300:'Light', 400:'Regular', 500:'Medium', 600:'SemiBold', 700:'Bold', 800:'ExtraBold', 900:'Black'}
SPECIMEN = 'Aa 0123 FPS 144'


def font_directory():
    return Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation)) / 'vela/fonts'


def cache_directory():
    return Path(QStandardPaths.writableLocation(QStandardPaths.GenericCacheLocation)) / 'vela/google-fonts'


def save_file(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    target = QSaveFile(str(path))
    if not target.open(QIODevice.WriteOnly) or target.write(data) != len(data) or not target.commit():
        raise OSError(target.errorString())


def decode_json(data):
    text = data.decode('utf-8-sig')
    if text.startswith(")]}'"): text = text.split('\n', 1)[1]
    return json.loads(text)


@dataclass(frozen=True)
class FontFamily:
    name: str
    category: str
    variants: tuple
    popularity: int = 99999

    @property
    def slug(self):
        safe = re.sub(r'[^a-z0-9]+', '-', self.name.lower()).strip('-')[:90]
        return safe + '-' + hashlib.sha256(self.name.encode()).hexdigest()[:8]

    @property
    def source(self):
        return 'https://fonts.google.com/specimen/' + self.name.replace(' ', '+')

    @property
    def legacy_slug(self):
        return {'Bebas Neue':'bebasneue', 'Patrick Hand':'patrickhand'}.get(self.name, self.slug.rsplit('-', 1)[0])

    def path(self, variant):
        # Existing Vela presets remain selectable without downloading again.
        legacy_slug = self.legacy_slug
        label = WEIGHTS.get(int(variant.rstrip('i')))
        if label:
            legacy = font_directory() / legacy_slug / (legacy_slug + '-' + label + ('Italic' if variant.endswith('i') else '') + '.ttf')
            if legacy.is_file(): return legacy
        return font_directory() / self.slug / (self.slug + '-' + variant + '.ttf')

    def preview_path(self, variant):
        return cache_directory() / 'previews' / (self.slug + '-' + variant + '.ttf')


def variant_label(variant):
    weight = int(variant.rstrip('i'))
    return f'{WEIGHTS.get(weight, "Weight")} {weight}' + (' · Italic' if variant.endswith('i') else '')


def parse_catalog(data):
    raw = decode_json(data)
    rows = raw.get('familyMetadataList', raw.get('families', []))
    families = []
    for row in rows:
        name = row.get('family', '')
        category = row.get('category', '').replace('Sans Serif', 'Sans serif')
        variants = tuple(sorted((v for v in row.get('fonts', {}) if re.fullmatch(r'(?:1000|[1-9]\d{0,2})i?', v)), key=lambda v:(v.endswith('i'),int(v.rstrip('i')))))
        if name and len(name)<200 and category in ('Monospace','Sans serif','Serif','Display','Handwriting') and variants:
            families.append(FontFamily(name, category, variants, int(row.get('popularity',99999))))
    if not families: raise ValueError('Google Fonts returned an empty or unsupported catalog')
    return sorted(families, key=lambda f:(f.popularity, f.name.casefold()))


def css_url(family, variant, preview=False):
    weight = int(variant.rstrip('i'))
    query = {'family': f'{family.name}:ital,wght@{int(variant.endswith("i"))},{weight}'}
    if preview: query['text'] = SPECIMEN
    return 'https://fonts.googleapis.com/css2?' + urlencode(query)


def parse_ttf_url(data):
    urls = re.findall(r'url\([\'"]?(https://[^\s)\'"]+)', data.decode('utf-8'))
    urls = list(dict.fromkeys(urls))
    if len(urls)!=1 or urlparse(urls[0]).hostname!='fonts.gstatic.com':
        raise ValueError('Google Fonts did not return a single desktop font')
    return urls[0]


def package_licenses(data):
    files = decode_json(data).get('manifest',{}).get('files', [])
    licenses = {}
    for item in files:
        name = Path(item.get('filename','')).name
        if name.upper() in ('OFL.TXT','LICENSE.TXT','LICENSE','LICENCE.TXT','UFL.TXT','COPYING','COPYING.TXT'):
            text = item.get('contents','')
            if len(text)>100 and ('license' in text.lower() or 'licence' in text.lower()): licenses[name]=text.encode()
    if not licenses: raise ValueError('The font package does not contain a license')
    return licenses


class GoogleFonts(QObject):
    catalog_changed = Signal()
    status_changed = Signal(str)
    font_ready = Signal(str, str, bool, str)
    font_failed = Signal(str, str, bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self.families = []
        self.inflight = set()
        self.manifests = {}
        self.refreshing = False
        self.last_refresh = 0.
        self.preview_queue = []
        self.active_previews = 0
        self.failed_previews = set()
        for source in (cache_directory()/'catalog.json', Path(__file__).parent/'assets/google-fonts.json'):
            try:
                self.families = parse_catalog(source.read_bytes()); break
            except (OSError,ValueError,KeyError,TypeError): pass

    def fetch(self, url, done, failed, limit=64*1024*1024):
        parsed=urlparse(url)
        if parsed.scheme!='https' or parsed.hostname not in ('fonts.google.com','fonts.googleapis.com','fonts.gstatic.com'):
            failed('Unexpected download source'); return
        request=QNetworkRequest(QUrl(url));request.setTransferTimeout(60000)
        request.setRawHeader(b'User-Agent', b'Vela/1.0') # Request static, desktop-compatible TrueType.
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute,QNetworkRequest.NoLessSafeRedirectPolicy)
        reply=self.network.get(request)
        reply.downloadProgress.connect(lambda received,total:reply.abort() if max(received,total)>limit else None)
        def finish():
            try:
                if reply.error()!=QNetworkReply.NoError: failed(reply.errorString());return
                data=bytes(reply.readAll())
                if len(data)>limit: failed('Download exceeds size limit');return
                done(data)
            finally: reply.deleteLater()
        reply.finished.connect(finish)

    def refresh(self, force=False):
        if self.refreshing or (not force and time.monotonic()-self.last_refresh<3600):return
        self.refreshing=True;self.status_changed.emit('Updating Google Fonts…')
        def failed(message):
            self.refreshing=False
            self.status_changed.emit('Offline catalog · refresh failed: '+message)
        def received(data):
            try:
                families=parse_catalog(data)
                save_file(cache_directory()/'catalog.json',data)
                self.families=families;self.failed_previews.clear();self.last_refresh=time.monotonic();self.refreshing=False
                self.catalog_changed.emit();self.status_changed.emit(f'Google Fonts · {len(families):,} families')
            except (ValueError,OSError,TypeError,KeyError) as error:failed(str(error))
        self.fetch(METADATA_URL,received,failed,8*1024*1024)

    def queue_preview(self,family,variant):
        key=(family.slug,variant,True)
        if family.path(variant).is_file() or family.preview_path(variant).is_file() or key in self.inflight or key in self.failed_previews:return
        if not any(f.slug==family.slug and v==variant for f,v in self.preview_queue):self.preview_queue.append((family,variant))
        self.pump_previews()

    def pump_previews(self):
        while self.active_previews<3 and self.preview_queue:
            family,variant=self.preview_queue.pop(0)
            self.active_previews+=1
            self.download(family,variant,True)

    def download(self,family,variant,preview=False):
        key=(family.slug,variant,preview)
        if key in self.inflight:return
        self.inflight.add(key)
        path=family.preview_path(variant) if preview else family.path(variant)
        def finish(error=None):
            self.inflight.discard(key)
            if error:
                if preview:self.failed_previews.add(key)
                self.font_failed.emit(family.slug,variant,preview,str(error))
            else:self.font_ready.emit(family.slug,variant,preview,str(path))
            if preview:
                self.active_previews-=1;self.pump_previews()
        def font_received(data):
            try:
                if data[:4] not in (b'\x00\x01\x00\x00',b'OTTO',b'ttcf'):raise ValueError('The server did not return a TrueType/OpenType font')
                save_file(path,data)
                if not preview:
                    save_file(path.parent/'family.json',json.dumps(dict(family=family.name,category=family.category,fonts={v:{} for v in family.variants},popularity=family.popularity)).encode())
                finish()
            except (ValueError,OSError) as error:finish(error)
        def css_received(data):
            try:self.fetch(parse_ttf_url(data),font_received,finish)
            except (ValueError,UnicodeError) as error:finish(error)
        def start_font():self.fetch(css_url(family,variant,preview),css_received,finish,1024*1024)
        def manifest_received(data):
            try:
                licenses=package_licenses(data);self.manifests[family.slug]=licenses
                for name,contents in licenses.items():save_file(path.parent/name,contents)
                start_font()
            except (ValueError,OSError,TypeError,KeyError) as error:finish(error)
        if preview:start_font()
        elif family.slug in self.manifests:
            try:
                for name,contents in self.manifests[family.slug].items():save_file(path.parent/name,contents)
                start_font()
            except OSError as error:finish(error)
        else:self.fetch('https://fonts.google.com/download/list?'+urlencode({'family':family.name}),manifest_received,finish,4*1024*1024)
