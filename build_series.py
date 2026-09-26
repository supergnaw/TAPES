#!/usr/bin/env python3
"""
Assembles training videos into Plex-ready MKV episodes with chapters.

Folder schema expected:
    <root>/
        01 Main Topic One/          ← Season 1
            01.01 Sub Topic One/    ← Episode 1
                01.01.01 Slide Title One.mp4   ← Chapter 1
                01.01.02 Slide Title Two.mp4   ← Chapter 2
                ...
            01.02 Sub Topic Two/    ← Episode 2
                ...
        02 Main Topic Two/          ← Season 2
            ...

Output (written to --output-dir, default: <root>/output):
    Season 01 - Main Topic One/
        S01E01 Sub Topic One.mkv
        S01E02 Sub Topic Two.mkv
    Season 02 - Main Topic Two/
        S02E01 Sub Topic Three.mkv

Requirements:
    • Python 3.7+
    • ffmpeg + ffprobe on PATH  (https://ffmpeg.org/download.html)

Usage:
    python build_training_series.py --root "C:/Training Videos"
    python build_training_series.py --root "C:/Training" --output-dir "D:/Plex/Training"
    python build_training_series.py --root "." --dry-run
    python build_training_series.py --root "." --season 2
    python build_training_series.py --root "." --season 2 --episode 3
"""
import argparse
from dataclasses import dataclass
import html
import re
import logger
import subprocess
import sys
import textwrap
from pathlib import Path

# ─── Regex patterns ──────────────────────────────────────────────────────────
RE_SEASON = re.compile(r"^(\d{2})\s+(.+)$")
RE_EPISODE = re.compile(r"^(\d{2})\.(\d{2})\s+(.+)$")
RE_CHAPTER = re.compile(r"^(\d{2})\.(\d{2})\.(\d{2,})\s+(.+)\.(mp4|mov|avi|mkv|wmv|m4v)$", re.IGNORECASE)


@dataclass
class BuildResult:
    ok: int = 0
    fail: int = 0
    skip: int = 0

    def __iadd__(self, other: "BuildResult"):
        self.ok += other.ok
        self.fail += other.fail
        self.skip += other.skip
        return self


class Chapter:
    ch_num: int = 0
    title: str
    ch_path: Path

    @property
    def chapter_name(self) -> str:
        return f"{self.ch_num:02d} - {self.title}"

    def __init__(self, ch_num: int, title: str, ch_path: Path):
        self.ch_num, self.title, self.ch_path = ch_num, title, ch_path


class Episode:
    se_num: int = 0
    ep_num: int = 0
    title: str
    ep_folder: Path

    @property
    def num_ch(self) -> int:
        return len(self.chapters)

    @property
    def plex_name(self) -> str:
        return f"S{self.se_num:02d}E{self.ep_num:02d} {self.title}"

    def __init__(self, se_num: int, ep_num: int, title: str, ep_folder: Path):
        self.se_num, self.ep_num, self.title, self.ep_folder = se_num, ep_num, title, ep_folder
        self.chapters: list[Chapter] = []
        self._scan_episode()

    def _scan_episode(self) -> None:
        for chapter_path in sorted(self.ep_folder.iterdir()):
            if chapter_path.is_dir(): continue
            mc = RE_CHAPTER.match(chapter_path.name)
            if not mc: continue

            new_chapter = Chapter(ch_num=int(mc.group(3)), title=mc.group(4).strip(), ch_path=chapter_path)

            self.chapters.append(new_chapter)
        self.chapters.sort(key=lambda ch: ch.ch_num)

    def build_episode(self, output_dir: Path, dry_run: bool = False) -> BuildResult:
        result = BuildResult()
        logger.info(f"  → {self.plex_name}")
        logger.log(
            logger.format(f"    {self.num_ch} chapter{'s' if self.num_ch != 1 else ''}: ", "bold", "magenta") +
            ", ".join(ch.title for ch in self.chapters[:5]) + ("..." if self.num_ch > 5 else "")
        )

        output_path = Path(f"{output_dir}/{self.plex_name}.mkv")

        # Dry run skip
        if dry_run:
            logger.log(
                logger.format(f"    [DRY RUN] ", "yellow") +
                logger.format(f"Would write: {output_path}", "bright blue")
            )
            result.ok += 1
            return result

        # Episode exists skip
        if output_path.exists():
            logger.log(
                logger.format(f"      [SKIP] ", "yellow") +
                logger.format(f"Already exists: {output_path}", "bright blue")
            )
            result.skip += 1
            return result

        # Normalize source chapter videos
        ts_files: list[Path] = []
        timestamps: list[float] = []
        current_timestamp: float = 0.0
        try:
            for ch in self.chapters:
                ts_path = output_dir / f"{self.plex_name}.ch{ch.ch_num:02d}.ts"
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(ch.ch_path),
                    "-c", "copy",
                    "-bsf:v", "h264_mp4toannexb",
                    "-f", "mpegts",
                    str(ts_path),
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    logger.error(proc.stderr)
                    result.fail += 1
                    return result

                # add new ts file, get timestamps, and log for funsies
                ts_files.append(ts_path)
                duration = self._probe_duration(ts_path)
                timestamps.append(duration)
                current_timestamp += duration
                logger.log(f"      {ch.chapter_name}  {self._format_timestamp(duration)}", "blue")

        except Exception as e:
            logger.log(
                logger.format("    [ERROR] ", "red", "bold") +
                str(e)
            )

        chapters_file = Path(f"{output_path}.chapters.txt").resolve()
        try:
            with chapters_file.open("w", encoding="utf-8") as f:
                cursor: float = 0
                lines: list = [";FFMETADATA1", f"title={self.title}"]
                for ch, ts in zip(self.chapters, timestamps):
                    lines += [
                        "\n[CHAPTER]",
                        "TIMEBASE=1/1000",
                        f"START={cursor}",
                        f"END={(ts * 1000) + cursor}",
                        f"title={ch.chapter_name}"
                    ]
                    cursor += ts * 1000
                f.write("\n".join(lines))

        except:
            logger.log(
                logger.format("    [ERROR] ", "red", "bold") +
                "Failed to create chapter metadata file."
            )

        # Final ffmpeg: concat TS → MKV + chapters
        cmd = [
            "ffmpeg", "-y",
            "-i", f"concat:{'|'.join(str(p) for p in ts_files)}",
            "-i", str(chapters_file),
            "-map", "0",
            "-map_chapters", "1",
            "-map_metadata", "1",
            "-c", "copy",
            str(output_path),
        ]

        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error(proc.stderr)
            result.fail += 1
            return result

        # Cleanup and return
        for ts_file in ts_files: ts_file.unlink()
        chapters_file.unlink()
        logger.success(f"      ✓ Done — {output_path.name}  ({self._format_timestamp(sum(timestamps))})")
        result.ok += 1
        return result

    def write_episode_nfo(self, output_dir: Path, summary: str = ""):
        """
        Creates: S01E01.nfo next to S01E01.mkv
        """
        nfo_path = output_dir / f"{self.plex_name}.nfo"
        num_nfo: int = 0

        xml = f"""<episodedetails>
      <title>{xml_escape(self.title)}</title>
      <season>{self.se_num}</season>
      <episode>{self.ep_num}</episode>
      <plot>{xml_escape(summary)}</plot>
    </episodedetails>
    """

        with nfo_path.open("w", encoding="utf-8") as f:
            logger.info(f"Writing NFO: {nfo_path}")
            f.write(xml)
            num_nfo += 1

        return num_nfo

    @staticmethod
    def _probe_duration(path: Path) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path)
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out)

    @staticmethod
    def _format_timestamp(timestamp: float) -> str:
        h = int(timestamp // 3600)
        m = int((timestamp % 3600) // 60)
        s = timestamp % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"


class Season:
    se_num: int = 0
    title: str
    se_folder: Path

    @property
    def num_ep(self) -> int:
        return len(self.episodes)

    @property
    def plex_folder(self) -> str:
        return f"Season {self.se_num:02d} - {self.title}"

    def __init__(self, se_num: int, title: str, se_folder: Path):
        self.se_num, self.title, self.se_folder = se_num, title, se_folder
        self.episodes: list[Episode] = []
        self._scan_season()

    def _scan_season(self) -> None:
        for episode_dir in sorted(self.se_folder.iterdir()):
            if not episode_dir.is_dir(): continue
            me = RE_EPISODE.match(episode_dir.name)
            if not me: continue

            new_episode = Episode(self.se_num, int(me.group(2)), me.group(3).strip(), episode_dir)
            if not new_episode: continue

            self.episodes.append(new_episode)
        self.episodes.sort(key=lambda ep: ep.ep_num)

    def build_season(self, output_dir: Path, dry_run: bool = False) -> BuildResult:
        result = BuildResult()
        if not output_dir.exists():
            if dry_run:
                logger.log(
                    logger.format(f"  [DRY RUN] ", "yellow") + logger.format(f"Would make directory: {output_dir}",
                                                                             "BrightBlue"))
            else:
                output_dir.mkdir(parents=True, exist_ok=True)
        for ep in self.episodes:
            result += ep.build_episode(output_dir, dry_run)

        return result

    def write_season_nfo(self, output_dir: Path, summary: str = "") -> int:
        """
        Creates: season01.nfo inside the season folder
        """
        n = f"{self.se_num:02d}"
        nfo_path = output_dir / self.plex_folder / f"season{n}.nfo"
        num_nfo: int = 0

        xml = f"""<season>
      <title>{xml_escape(self.title)}</title>
      <seasonnumber>{self.se_num}</seasonnumber>
      <plot>{xml_escape(summary)}</plot>
    </season>
    """

        with nfo_path.open("w", encoding="utf-8") as f:
            logger.info(f"Writing NFO: {nfo_path}")
            f.write(xml)
        num_nfo += 1

        for ep in self.episodes:
            num_nfo += ep.write_episode_nfo(output_dir / self.plex_folder)

        return num_nfo


class Series:
    root_folder: Path
    output_dir: Path
    title: str

    @property
    def num_se(self) -> int:
        return len(self.seasons)

    def __init__(self, root_folder: Path, output_dir: Path):
        self.root_folder, self.output_dir, self.title = root_folder, output_dir, output_dir.name
        self.seasons: list[Season] = []
        self._scan_series()

    def _scan_series(self) -> None:
        for season_dir in sorted(self.root_folder.iterdir()):
            if not season_dir.is_dir(): continue
            ms = RE_SEASON.match(season_dir.name)
            if not ms: continue

            new_season = Season(int(ms.group(1)), ms.group(2).strip(), season_dir)
            if not new_season: continue

            self.seasons.append(new_season)
        self.seasons.sort(key=lambda se: se.se_num)

    def show_overview(self) -> None:
        total_se = len(self.seasons)
        total_eps = sum(s.num_ep for s in self.seasons)
        total_chap = sum(e.num_ch for s in self.seasons for e in s.episodes)

        title_line = f" {self.title} "
        stats_line = " · ".join([
            logger.format(" " + str(total_se), "green", "bold") + " seasons",
            logger.format(str(total_eps), "green", "bold") + " episodes",
            logger.format(str(total_chap), "green", "bold") + " chapters "
        ])
        max_width = len(title_line) + 20
        logger.log(f"{title_line:=^{max_width}}")
        logger.log(f"{stats_line:-^{max_width + 33}}\n")

        for s in self.seasons:
            logger.log(
                f"  {logger.format(s.plex_folder, 'underline', 'bold')}  {logger.format(f'({s.num_ep} ep)', 'bright yellow')}")
            for e in s.episodes:
                logger.log(
                    f"    {logger.format(e.plex_name, 'cyan')}  {logger.format(f'({e.num_ch} chapters)', 'bold', 'blue')}")
            logger.log("")

    def build_series(self, season: int = 0, episode: int = 0, dry_run: bool = False) -> BuildResult:
        result = BuildResult()

        # Filter
        if 0 < season:
            self.seasons = [s for s in self.seasons if s.se_num == season]
            if not self.seasons: logger.error(f"Season {season} not found."); sys.exit()
            if 0 < episode:
                for s in self.seasons:
                    s.episodes = [e for e in s.episodes if e.ep_num == episode]

        for se in self.seasons:
            output_dir = Path(f"{self.output_dir}/{se.plex_folder}").resolve()
            result += se.build_season(output_dir, dry_run)
        return result

    def write_series_nfo(self, summary: str = "") -> int:
        """
        Creates: tvshow.nfo in the series root folder
        """
        nfo_path = self.output_dir / f"{self.title}.nfo"
        num_nfo: int = 0

        xml = f"""<tvshow>
      <title>{xml_escape(self.title)}</title>
      <plot>{xml_escape(summary)}</plot>
    </tvshow>
    """

        with nfo_path.open("w", encoding="utf-8") as f:
            logger.info(f"Writing NFO: {nfo_path}")
            f.write(xml)
        num_nfo += 1

        for se in self.seasons:
            num_nfo += se.write_season_nfo(self.output_dir)

        return num_nfo


def parse_args():
    p = argparse.ArgumentParser(
        description="Assembles training videos into Plex-ready MKV episodes with chapters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              python build_training_series.py --root "C:/Training"
              python build_training_series.py --root "C:/Training" --output-dir "D:/Plex"
              python build_training_series.py --root "." --dry-run
              python build_training_series.py --root "." --season 2
              python build_training_series.py --root "." --season 2 --episode 3
        """))
    p.add_argument("--root", required=True)
    p.add_argument("--output-dir", default=None)
    p.add_argument("--season", type=int, default=0)
    p.add_argument("--episode", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--log", default="build.log")
    p.add_argument("--ffmpeg-args", default="")
    return p.parse_args()


def check_ffmpeg(ignore: bool = False) -> bool:
    """Verify that both ffmpeg and ffprobe are reachable on PATH before doing any work."""
    if ignore:
        logger.info("Skipping ffmpeg checks...")
        return
    else:
        logger.info("Verifying ffmpeg installation...")

    missing = []
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run(
                args=[tool, "-version"],
                capture_output=True,
                check=True
            )
        except FileNotFoundError:
            missing.append(tool)
        except subprocess.CalledProcessError:
            pass  # present but returned non-zero — still counts as found

    if missing:
        logger.error(f"\n[ERROR] The following required tool(s) were not found on your PATH:")
        for tool in missing:
            logger.error(f"          • {tool}")
        logger.warning("\n  Install ffmpeg and ensure both ffmpeg and ffprobe are on your PATH.")
        logger.warning("  Download: https://ffmpeg.org/download.html")
        logger.warning("  Windows:  run command `winget install \"FFmpeg (Essentials Build)\"`")
        logger.warning("  macOS:    brew install ffmpeg")
        logger.warning("  Linux:    sudo apt install ffmpeg   (or equivalent for your distro)\n")
        return False

    # Confirm versions found
    for tool in ("ffmpeg", "ffprobe"):
        result = subprocess.run([tool, "-version"], capture_output=True, text=True)
        version_line = result.stdout.splitlines()[0] if result.stdout else "(unknown version)"
        print(
            f"  {logger.format('✓', 'Bright Green', 'bold')} {logger.format(tool, 'bright white')}: {logger.format(version_line, 'blue', 'underline')}")
    return True


def xml_escape(s: str) -> str:
    return html.escape(s, quote=True)


def main():
    args = parse_args()
    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else root / "output"
    ffmpeg_extra = args.ffmpeg_args.split() if args.ffmpeg_args else []

    if not check_ffmpeg():
        sys.exit()

    if not root.exists():
        logger.error(f"[ERROR] Root directory not found: {root}")
        sys.exit()

    logger.log("\n╔════════════════════════════════════════╗", "brightmagenta", "bold")
    logger.log(
        logger.format("║  ", "bright magenta", "bold") + logger.format("Custom Series MKV Assembler", "bright cyan",
                                                                       "bold") + logger.format("           ║",
                                                                                               "bright magenta",
                                                                                               "bold"))
    logger.log("╚════════════════════════════════════════╝", "brightmagenta", "bold")
    logger.log(
        logger.format("  Root .......: ", "bright yellow") + logger.format(f"\"{root}\"\n", "cyan", "bold") +
        logger.format("  Output .....: ", "bright yellow") + logger.format(f"\"{output_dir}\"\n", "cyan", "bold") +
        logger.format("  Dry run ....: ", "bright yellow") + logger.format(f"{args.dry_run}\n",
                                                                           "green" if args.dry_run else "red", "bold")
    )

    logger.info("Build started.\n")

    library = Series(root_folder=root, output_dir=output_dir)
    if not library.seasons:
        logger.error("[ERROR] No season folders found.")
        sys.exit()

    library.show_overview()
    result = library.build_series(season=args.season, episode=args.episode, dry_run=args.dry_run)
    logger.bold(("-" * 64) + "\n")
    num_nfo_files = library.write_series_nfo()
    logger.bold(("-" * 64) + "\n")
    logger.log(
        f"  {logger.format(f'✓ Built', 'bright green')}: {logger.format(f' {result.ok} ', 'bold', 'framed')}  |" +
        f"  {logger.format(f'Skipped', 'cyan')}: {logger.format(f' {result.skip} ', 'bold', 'framed')}  |" +
        f"  {logger.format(f'✗ Failed', 'red')}: {logger.format(f' {result.fail} ', 'bold', 'framed')}  |"
        f"  {logger.format(f'NFO files', 'blue')}: {logger.format(f' {num_nfo_files} ', 'bold', 'framed')}\n"
    )

    if not args.dry_run and result.ok:
        logger.success(f"MKV files written to: {output_dir}")

    logger.info("Build complete!")


if "__main__" == __name__:
    main()
