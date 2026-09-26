# TAPES
**Training Assembly & Production Episode System**

TAPES is a Python-based build pipeline designed to transform large collections of short training clips into fully produced episodes and seasons. It handles video normalization, chapter stitching, metadata generation, Plex-friendly organization, and optional audiobook output in one automated workflow.

---

## Features

### Episode & Season Assembly
- Combine dozens or hundreds of short training clips into cohesive episodes.
- Automatically generate chapter markers and timestamps.
- Build full seasons with consistent naming and structure.

### Metadata Generation *(incomplete)*
- Create Plex-compatible `.nfo` files for:
  - Series (`tvshow.nfo`)
  - Seasons (`seasonXX.nfo`)
  - Episodes (`SxxEyy.nfo`)
- Auto-generate summaries (filename-based or chapter-based).
- Embed MKV metadata such as titles and chapters.

### Artwork Support *(incomplete)*
- Optional local posters and thumbnails:
  - `poster.jpg` (series)
  - `seasonXX-poster.jpg` (season)
  - `SxxEyy-thumb.jpg` (episode)
- Compatible with Plex’s Local Media Assets agent.

### Audiobook Output *(incomplete)*
- Extract audio from episodes.
- Build `.m4b` audiobook files with chapters and cover art.
- Perfect for listening on the go, during chores, or while relaxing.

### Captioning *(incomplete)*
- Whisper-based automatic transcription.
- Generate `.srt` caption files.
- Embed subtitles into MKVs.

---

## Usage

Run TAPES to:
1. Normalize and stitch chapter clips.
2. Build MKV episodes.
3. Generate metadata and artwork.
4. (Optional) Produce audiobook versions.
5. Output a complete, Plex-ready season.

Configuration options include:
- Input directory
- Output directory
- Rendering a single season or episode
- Dry-run to see what would happen
- Logging settings

---

## License

This project is for personal use.  
Feel free to adapt or extend it for your own training series workflows.
