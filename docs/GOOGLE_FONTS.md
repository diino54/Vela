# Google Fonts in Vela

Open the presets icon next to either font field. The browser exposes the full
Google Fonts catalog with category filters, search, popularity/alphabetical
sorting, weight and italic styles, and 24 families per page. Visible tiles
fetch small text-only specimens, at most three concurrently. Download font
fetches a complete static desktop TTF for the selected style plus the package
license. Use font applies it through the existing Vela appearance controls.

The catalog ships with a metadata snapshot (2026-10-31), loads a newer local
cache when available, and refreshes from fonts.google.com/metadata/fonts.
Refresh retries manually; cached catalogs and downloaded fonts work offline.
The metadata and package-manifest endpoints are used by Google's website and
may change; malformed responses preserve the previous catalog. No API key is
required. This is a catalog browser, not an embedded web page.

Font resolution uses the [Google Fonts CSS2 API](https://developers.google.com/fonts/docs/css2)
with an explicit weight/italic pair and a desktop user agent. Specimen requests
use text subsetting. Package licenses come from Google's download/list manifest;
only complete fonts, never the specimen subsets, are applied to MangoHud.
Custom width/optical-size axes use the family's defaults.

Font files and licenses live in $XDG_DATA_HOME/vela/fonts (default
~/.local/share/vela/fonts). Catalog and specimen caches use
$XDG_CACHE_HOME/vela/google-fonts (default ~/.cache/vela/google-fonts).
Existing Vela presets remain usable and appear in Downloaded.

Validation: 17 unit tests; live catalog refresh (1,959 families); full static
TTF downloads and license checks for JetBrains Mono Bold Italic, Roboto, Lobster
and Noto Sans JP; actual visible-tile previews; pagination, bounded widget
cache, empty searches, interrupted modal transitions and preview restoration.
