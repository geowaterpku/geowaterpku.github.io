from __future__ import annotations

import html as html_lib
import os
import re
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

# Conservative defaults: large enough for desktop displays, materially smaller on the wire.
CONVERT_MIN_BYTES = 300 * 1024
RECOMPRESS_WEBP_MIN_BYTES = 450 * 1024
DEFAULT_MAX_DIM = 2000
WEBP_QUALITY = 88

# High-impact files discovered in the repository audit.
FORCED_MAX_DIM = {
    "assets/headshot.png": 1000,
    "assets/home/background1.png": 1800,
    "assets/home/geowater-human-background.png": 1800,
    "assets/research/geowater-overview-v2.png": 1800,
}

# These files benefit from responsive srcset variants because they are displayed prominently.
RESPONSIVE_WIDTHS = {
    "assets/headshot.webp": (480, 800, 1000),
    "assets/home/background1.webp": (640, 960, 1440),
    "assets/home/geowater-human-background.webp": (640, 960, 1440),
    "assets/research/geowater-overview-v2.webp": (640, 960, 1440),
}

TEXT_SUFFIXES = {".html", ".css", ".js", ".json", ".md", ".yml", ".yaml"}
SKIP_IMAGE_PARTS = {"logos"}

changed_files: set[str] = set()
reference_map: dict[str, str] = {}
responsive_map: dict[str, list[tuple[int, str]]] = {}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def ensure_rgb(img: Image.Image) -> Image.Image:
    if img.mode in {"RGBA", "LA"}:
        return img.convert("RGBA")
    if img.mode == "P" and "transparency" in img.info:
        return img.convert("RGBA")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def resized_copy(img: Image.Image, max_dim: int) -> Image.Image:
    img = ImageOps.exif_transpose(img)
    if max(img.size) <= max_dim:
        return img.copy()
    copy = img.copy()
    copy.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return copy


def save_webp(img: Image.Image, target: Path, *, quality: int = WEBP_QUALITY) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = ensure_rgb(img)
    clean.save(target, "WEBP", quality=quality, method=6, optimize=True)


def convert_large_rasters() -> None:
    candidates = sorted(
        p for p in ASSETS.rglob("*")
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )

    for source in candidates:
        source_rel = rel(source)
        if any(part in SKIP_IMAGE_PARTS for part in source.parts):
            continue
        forced = source_rel in FORCED_MAX_DIM
        if not forced and source.stat().st_size < CONVERT_MIN_BYTES:
            continue

        try:
            with Image.open(source) as opened:
                if getattr(opened, "is_animated", False):
                    continue
                max_dim = FORCED_MAX_DIM.get(source_rel, DEFAULT_MAX_DIM)
                optimized = resized_copy(opened, max_dim)
                target = source.with_suffix(".webp")
                with NamedTemporaryFile(suffix=".webp", delete=False) as tmp_file:
                    tmp = Path(tmp_file.name)
                try:
                    save_webp(optimized, tmp, quality=90 if forced else WEBP_QUALITY)
                    new_size = tmp.stat().st_size
                    old_size = source.stat().st_size
                    # Forced files are known bottlenecks. Generic conversions must be clearly worthwhile.
                    if forced or new_size <= old_size * 0.85:
                        target.write_bytes(tmp.read_bytes())
                        reference_map[source_rel] = rel(target)
                        changed_files.add(rel(target))
                        print(f"converted {source_rel}: {old_size/1024:.0f} KB -> {new_size/1024:.0f} KB")
                finally:
                    tmp.unlink(missing_ok=True)
        except Exception as exc:
            print(f"skip {source_rel}: {exc}")


def recompress_large_webp() -> None:
    for source in sorted(ASSETS.rglob("*.webp")):
        if not source.is_file() or source.stat().st_size < RECOMPRESS_WEBP_MIN_BYTES:
            continue
        if any(part in SKIP_IMAGE_PARTS for part in source.parts):
            continue
        try:
            with Image.open(source) as opened:
                if getattr(opened, "is_animated", False):
                    continue
                optimized = resized_copy(opened, DEFAULT_MAX_DIM)
                with NamedTemporaryFile(suffix=".webp", delete=False) as tmp_file:
                    tmp = Path(tmp_file.name)
                try:
                    save_webp(optimized, tmp)
                    old_size = source.stat().st_size
                    new_size = tmp.stat().st_size
                    if new_size <= old_size * 0.90:
                        source.write_bytes(tmp.read_bytes())
                        changed_files.add(rel(source))
                        print(f"recompressed {rel(source)}: {old_size/1024:.0f} KB -> {new_size/1024:.0f} KB")
                finally:
                    tmp.unlink(missing_ok=True)
        except Exception as exc:
            print(f"skip {rel(source)}: {exc}")


def generate_responsive_variants() -> None:
    for source_rel, widths in RESPONSIVE_WIDTHS.items():
        source = ROOT / source_rel
        if not source.exists():
            continue
        try:
            with Image.open(source) as opened:
                base = ImageOps.exif_transpose(opened)
                source_width, _ = base.size
                variants: list[tuple[int, str]] = []
                for width in widths:
                    if width >= source_width:
                        continue
                    ratio = width / source_width
                    height = max(1, round(base.height * ratio))
                    resized = base.resize((width, height), Image.Resampling.LANCZOS)
                    target = source.with_name(f"{source.stem}-{width}.webp")
                    save_webp(resized, target, quality=88)
                    variants.append((width, rel(target)))
                    changed_files.add(rel(target))
                variants.append((source_width, source_rel))
                responsive_map[source_rel] = sorted(set(variants))
        except Exception as exc:
            print(f"responsive variants skipped for {source_rel}: {exc}")


def replace_references() -> None:
    if not reference_map:
        return
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or ".git" in path.parts:
            continue
        original = path.read_text(encoding="utf-8")
        updated = original
        for old_root, new_root in reference_map.items():
            updated = updated.replace(old_root, new_root)
            old_path = ROOT / old_root
            new_path = ROOT / new_root
            old_local = os.path.relpath(old_path, path.parent).replace(os.sep, "/")
            new_local = os.path.relpath(new_path, path.parent).replace(os.sep, "/")
            updated = updated.replace(old_local, new_local)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.add(rel(path))


def get_attr(tag: str, name: str) -> str | None:
    match = re.search(rf"\b{name}\s*=\s*([\"'])(.*?)\1", tag, flags=re.I | re.S)
    return html_lib.unescape(match.group(2)) if match else None


def set_attr(tag: str, name: str, value: str, *, force: bool = False) -> str:
    pattern = rf"\b{name}\s*=\s*([\"']).*?\1"
    if re.search(pattern, tag, flags=re.I | re.S):
        if not force:
            return tag
        return re.sub(pattern, f'{name}="{value}"', tag, count=1, flags=re.I | re.S)
    closing = "/>" if tag.rstrip().endswith("/>") else ">"
    pos = tag.rfind(closing)
    return tag[:pos] + f' {name}="{value}"' + tag[pos:]


def resolve_local_asset(html_path: Path, src: str) -> Path | None:
    src = src.split("?", 1)[0].split("#", 1)[0]
    if not src or src.startswith(("http://", "https://", "//", "data:")):
        return None
    if src.startswith("/"):
        candidate = ROOT / src.lstrip("/")
    else:
        candidate = html_path.parent / src
    try:
        candidate = candidate.resolve()
        candidate.relative_to(ROOT.resolve())
    except Exception:
        return None
    return candidate if candidate.exists() else None


def image_dimensions(path: Path) -> tuple[int, int] | None:
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return None
    try:
        with Image.open(path) as img:
            return img.size
    except Exception:
        return None


def is_critical_image(page: str, src: str) -> bool:
    clean = src.split("?", 1)[0]
    critical = {
        "peirong-lin.html": ("assets/headshot.webp",),
        "people.html": ("assets/headshot.webp",),
        "current-research.html": ("assets/research/geowater-overview-v2.webp",),
    }
    return any(item in clean for item in critical.get(page, ()))


def responsive_sizes(src: str) -> str:
    if "headshot" in src:
        return "(max-width: 700px) 60vw, 320px"
    return "(max-width: 900px) calc(100vw - 40px), 50vw"


def enhance_html_images() -> None:
    for path in sorted(ROOT.glob("*.html")):
        original = path.read_text(encoding="utf-8")

        def enhance(match: re.Match[str]) -> str:
            tag = match.group(0)
            src = get_attr(tag, "src")
            if not src:
                return tag
            critical = is_critical_image(path.name, src)
            tag = set_attr(tag, "decoding", "async")
            tag = set_attr(tag, "loading", "eager" if critical else "lazy", force=critical)
            if critical:
                tag = set_attr(tag, "fetchpriority", "high")

            asset = resolve_local_asset(path, src)
            if asset:
                dims = image_dimensions(asset)
                if dims:
                    tag = set_attr(tag, "width", str(dims[0]))
                    tag = set_attr(tag, "height", str(dims[1]))

            clean_src = src.split("?", 1)[0]
            root_src = clean_src.lstrip("/")
            variants = responsive_map.get(root_src)
            if variants and not get_attr(tag, "srcset"):
                srcset = ", ".join(f"{variant} {width}w" for width, variant in variants)
                tag = set_attr(tag, "srcset", srcset)
                tag = set_attr(tag, "sizes", responsive_sizes(src))
            return tag

        updated = re.sub(r"<img\b[^>]*>", enhance, original, flags=re.I | re.S)

        # Do not preload entire autoplay videos before they are needed; metadata is enough to establish layout.
        def enhance_video(match: re.Match[str]) -> str:
            tag = match.group(0)
            return set_attr(tag, "preload", "metadata")

        updated = re.sub(r"<video\b[^>]*>", enhance_video, updated, flags=re.I | re.S)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.add(rel(path))


def optimize_home_loading() -> None:
    # Remove remote Google Fonts imports. Existing font stacks fall back locally instead of blocking on cross-border requests.
    for css_name in ("assets/styles.css", "assets/home-v2.css"):
        path = ROOT / css_name
        if not path.exists():
            continue
        original = path.read_text(encoding="utf-8")
        updated = re.sub(
            r"@import\s+url\([^;]*fonts\.googleapis\.com[^;]*;\s*",
            "",
            original,
            flags=re.I,
        )
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed_files.add(css_name)

    # Content must be readable immediately. Scroll animation is now progressive enhancement, not a visibility gate.
    home_css = ROOT / "assets/home-v2.css"
    if home_css.exists():
        original = home_css.read_text(encoding="utf-8")
        updated = re.sub(
            r"\.reveal-on-scroll\{opacity:0;transform:translateY\(28px\);transition:[^}]+\}\s*"
            r"\.reveal-on-scroll\.is-visible\{opacity:1;transform:none\}",
            ".reveal-on-scroll{opacity:1;transform:none}\n.reveal-on-scroll.is-visible{opacity:1;transform:none}",
            original,
            flags=re.S,
        )
        if updated != original:
            home_css.write_text(updated, encoding="utf-8")
            changed_files.add(rel(home_css))

    # Keep the current rendered hero (river-city) but declare it directly in CSS so the browser does not fetch one image then swap it in JS.
    editorial_css = ROOT / "assets/home-editorial.css"
    if editorial_css.exists():
        original = editorial_css.read_text(encoding="utf-8")
        updated = original.replace(
            'background: #06182a url("home/geowater-hero-satellite-v1.webp") center center / cover no-repeat;',
            'background: #06182a url("home/geowater-river-city-v1.webp") center center / cover no-repeat;',
            1,
        )
        closing_rule = """

/* Performance: declare the closing visual in CSS instead of discovering it after JS execution. */
.lab-home-v2 .home-v2-closing {
  background:
    linear-gradient(90deg, rgba(3, 27, 44, .9) 0%, rgba(4, 38, 59, .76) 48%, rgba(6, 42, 62, .4) 100%),
    linear-gradient(0deg, rgba(3, 23, 38, .48), rgba(3, 23, 38, .08) 58%),
    url("home/geowater-hero-satellite-v1.webp") center center / cover no-repeat;
}
"""
        if "Performance: declare the closing visual" not in updated:
            updated += closing_rule
        if updated != original:
            editorial_css.write_text(updated, encoding="utf-8")
            changed_files.add(rel(editorial_css))

    home_js = ROOT / "assets/home-v2.js"
    if home_js.exists():
        original = home_js.read_text(encoding="utf-8")
        updated = re.sub(
            r"\n\s*// Visual test: exchange the hero and closing background images.*?\n\s*const newsSection",
            "\n\n  const newsSection",
            original,
            count=1,
            flags=re.S,
        )
        # Respect the authored heading in index.html and remove an unnecessary runtime text mutation.
        updated = re.sub(
            r"\n\s*const questionsTitle = document\.querySelector\('#questions-title'\);\s*"
            r"if \(questionsTitle\) questionsTitle\.textContent = 'Three questions guide our science\.';\s*",
            "\n",
            updated,
            count=1,
            flags=re.S,
        )
        if updated != original:
            home_js.write_text(updated, encoding="utf-8")
            changed_files.add(rel(home_js))

    index = ROOT / "index.html"
    if index.exists():
        original = index.read_text(encoding="utf-8")
        updated = original
        hero = "assets/home/geowater-river-city-v1.webp"
        if f'href="{hero}" fetchpriority="high"' not in updated:
            preload = f'  <link rel="preload" as="image" href="{hero}" fetchpriority="high">\n'
            marker = '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            if marker in updated:
                updated = updated.replace(marker, marker + preload, 1)
            else:
                updated = updated.replace("</head>", preload + "</head>", 1)
        if updated != original:
            index.write_text(updated, encoding="utf-8")
            changed_files.add(rel(index))


def optimize_contact_video() -> None:
    source = ROOT / "assets/contact/peking.mp4"
    ffmpeg = shutil.which("ffmpeg")
    if not source.exists() or not ffmpeg:
        return
    tmp = source.with_name("peking.optimized.mp4")
    try:
        subprocess.run(
            [
                ffmpeg, "-y", "-i", str(source),
                "-vf", "scale='min(1280,iw)':-2",
                "-an", "-c:v", "libx264", "-crf", "29", "-preset", "medium",
                "-movflags", "+faststart", str(tmp),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if tmp.exists() and tmp.stat().st_size <= source.stat().st_size * 0.90:
            old_size = source.stat().st_size
            source.write_bytes(tmp.read_bytes())
            changed_files.add(rel(source))
            print(f"recompressed {rel(source)}: {old_size/1024:.0f} KB -> {source.stat().st_size/1024:.0f} KB")
    except Exception as exc:
        print(f"video optimization skipped: {exc}")
    finally:
        tmp.unlink(missing_ok=True)


def main() -> None:
    convert_large_rasters()
    recompress_large_webp()
    generate_responsive_variants()
    replace_references()
    enhance_html_images()
    optimize_home_loading()
    optimize_contact_video()

    print("\nChanged/generated files:")
    for name in sorted(changed_files):
        print(f" - {name}")
    print(f"Total: {len(changed_files)}")


if __name__ == "__main__":
    main()
