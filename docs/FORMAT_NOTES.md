# DJ Software Format Notes

Reference documentation for the file formats used by each supported DJ platform. This is the research that drives the converter implementations.

---

## Rekordbox (Pioneer DJ)

### File used

**`rekordbox.xml`** — exported from Rekordbox via _File > Export Collection in XML Format_.

> ConaConverter does **not** read `master.db` (Rekordbox 6's internal database), which is encrypted with SQLCipher. The XML export is Pioneer's documented interchange format and is the correct way to move data in and out of Rekordbox.

### XML structure

```xml
<DJ_PLAYLISTS Version="1.0.0">
  <PRODUCT Name="rekordbox" Version="6.x" Company="Pioneer DJ"/>
  <COLLECTION Entries="N">
    <TRACK TrackID="1" Name="Track Title" Artist="Artist Name"
           Album="Album" Genre="Techno" TotalTime="240"
           AverageBpm="128.00" Tonality="8m"
           Location="file://localhost/C:/Music/track.mp3">
      <POSITION_MARK Name="Intro" Type="0" Start="4.123" Num="0"
                     Red="40" Green="226" Blue="20"/>
      <TEMPO Inizio="0.150" Bpm="128.00" Metro="4/4" Battito="1"/>
    </TRACK>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT">
      <NODE Name="My Playlist" Type="1" KeyType="0" Entries="1">
        <TRACK Key="1"/>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
```

### POSITION_MARK attributes

| Attribute | Description |
|---|---|
| `Type` | `0` = cue, `1` = fade-in, `2` = fade-out, `3` = load, `4` = loop |
| `Num` | `-1` = memory cue; `0–8` = hot cue slot |
| `Start` | Position in **seconds** (float string, e.g. `"4.123"`) |
| `End` | Loop end in seconds (loops only) |
| `Red`, `Green`, `Blue` | Color components 0–255 |
| `Name` | Label string |

### TEMPO (beat grid) attributes

| Attribute | Description |
|---|---|
| `Inizio` | Position of beat 1 in seconds |
| `Bpm` | BPM at this marker |
| `Metro` | Time signature (e.g. `"4/4"`) |
| `Battito` | Beat number within the bar |

### File paths

Rekordbox stores paths as `file://localhost/C:/Music/track.mp3` (Windows) or `file://localhost/Users/name/Music/track.mp3` (macOS). ConaConverter strips the `file://localhost` prefix on read and restores it on write.

### References

- [Pioneer DJ Rekordbox XML Format PDF](https://cdn.rekordbox.com/files/20200410160904/xml_format_list.pdf)
- [pyrekordbox library](https://github.com/dylanljones/pyrekordbox)

---

## Serato DJ

### Files used

| File | Purpose |
|---|---|
| `_Serato_/SubCrates/*.crate` | Playlist/crate membership — list of track file paths |
| `_Serato_/database V2` | Full library index (binary, no extension) |
| GEOB ID3 tags in audio files | Cue points, beat grid, waveform data |

### Crate format

`.crate` files are small binary files. Each crate records the absolute paths of tracks it contains, plus any Serato-specific per-track metadata the user has set within that crate context.

Parsed using the [`serato-tools`](https://github.com/bvandercar-vt/serato-tools) library.

### GEOB ID3 tags

Serato stores per-track cue and grid data by embedding custom GEOB tags directly into the audio files themselves. This is Serato's architecture — the `.crate` file only stores membership, not analysis data.

| Tag name | Contents |
|---|---|
| `Serato Markers2` | Hot cues, memory cues, loops, track color |
| `Serato BeatGrid` | Beat grid anchor points (sample offset + BPM) |
| `Serato Overview` | Waveform overview data |

**Cue positions** in `Serato Markers2` are stored in **milliseconds**.
**Beat grid positions** are stored in **samples** (sample offset from the start of the file).

### Write behaviour

Writing to Serato embeds the converted cue/grid data back into the audio files as GEOB tags. The `.crate` file records the track list. ConaConverter shows a warning dialog before any Serato write because **audio files are modified**.

### Platform locations

| OS | Location |
|---|---|
| Windows | `C:\Users\{name}\Music\_Serato_\` |
| macOS | `/Users/{name}/Music/_Serato_/` |

### References

- [Mixxx: Serato Database Format](https://github.com/mixxxdj/mixxx/wiki/Serato-Database-Format)
- [Mixxx: Serato Metadata Format](https://github.com/mixxxdj/mixxx/wiki/Serato-Metadata-Format)
- [serato-tools library](https://github.com/bvandercar-vt/serato-tools)

---

## Engine OS (Denon DJ)

### Files used

Engine OS uses two SQLite database files:

| File | Contents |
|---|---|
| `m.db` | Track metadata: title, artist, album, genre, BPM, key, file paths. Also Playlist and PlaylistTrack tables. |
| `p.db` | Performance data: cue points, beat grid, waveform overview — stored as compressed BLOBs in the `PerformanceData` table. |

Default location on desktop:

| OS | Location |
|---|---|
| Windows | `C:\Users\{name}\Music\Engine Library\` |
| macOS | `/Users/{name}/Music/Engine Library/` |

### BLOB encoding

All BLOB columns in `PerformanceData` (except `loops`) use the same encoding:

```
[ 4 bytes: uncompressed length, big-endian uint32 ]
[ N bytes: zlib-compressed payload ]
```

Decode in Python:
```python
import struct, zlib

def decode_blob(data: bytes) -> bytes:
    uncompressed_len = struct.unpack(">I", data[:4])[0]
    return zlib.decompress(data[4:])
```

### quickCues BLOB layout

8 fixed slots (one per hot cue slot 0–7), packed sequentially:

```
For each slot (0 to 7):
  label_length  [u8]        — length of label in bytes
  label         [utf-8]     — label bytes (label_length bytes)
  position      [i32 BE]    — position in milliseconds; -1 = empty slot
  color         [u32 BE]    — 0x00RRGGBB; 0 = no color
```

### beatGrid BLOB layout

```
num_markers  [u32 BE]   — number of beat markers

For each marker:
  sample_number  [u64 BE]   — sample offset of this beat
  bpm_x100       [u32 BE]   — BPM × 100 (e.g. 12800 = 128.00 BPM)
```

Convert sample offset to seconds: `seconds = sample_number / sample_rate`

### Schema versioning

The `Information` table contains a `schemaVersion` column. ConaConverter reads this on open and refuses to write to databases with an unrecognised version to avoid corruption.

### Critical constraints

- **Never open or modify Engine OS databases while Engine DJ is running** — the app holds a write lock.
- **Never write to a hardware device's database directly** — always write to the desktop Engine Library and let Engine DJ sync to hardware (USB drives, SD cards) through its normal export process.
- The schema is version-tagged; Denon has documented that third-party tools must not alter the schema.

### References

- [Mixxx: Engine Library Format](https://github.com/mixxxdj/mixxx/wiki/Engine-Library-Format)
- [Engine DJ v3.0 Third-Party Tool Support](https://enginedj.com/kb/solutions/69000834165/engine-dj-v3-0-support-for-third-party-database-tools)

---

## VirtualDJ

### File used

**`database.xml`** — VirtualDJ's main library database.

Location:
| OS | Location |
|---|---|
| Windows | `Documents\VirtualDJ\database.xml` |
| macOS | `~/Documents/VirtualDJ/database.xml` |
| External drive | `{drive}/VirtualDJ/database.xml` |

### XML structure

```xml
<VirtualDJ_Database Version="8.5">
  <Song FilePath="C:\Music\track.mp3" FileSize="8000000">
    <Tags Author="Artist" Title="Title" Genre="Techno" Album="Album"/>
    <Infos SongLength="240.500" Bitrate="320"/>
    <Scan Version="801" Bpm="0.468750" Volume="0.8" Key="8m"/>
    <Poi Pos="-0.002" Type="beatgrid" Name=""/>
    <Poi Pos="4.123"  Type="cue"      Num="0" Name="Intro" Color="#28E214"/>
    <Poi Pos="16.000" Type="loop"     Num="0" Name=""      Size="16.000"/>
  </Song>
</VirtualDJ_Database>
```

### Poi (Point of Interest) types

| `Type` | Meaning |
|---|---|
| `cue` | Hot cue |
| `beatgrid` | Beat grid anchor point |
| `loop` | Loop start; `Size` attribute is loop length in seconds |
| `automix` | Automix transition point (treated as memory cue) |
| `fade` | Fade in/out point |

All `Pos` values are in **seconds** — no conversion needed.

### BPM storage

> **Critical:** `Scan/@Bpm` stores **seconds-per-beat**, NOT beats-per-minute.

```
BPM = 60.0 / Scan_Bpm_value
Scan_Bpm_value = 60.0 / BPM

Example: Bpm="0.468750" → 60.0 / 0.468750 = 128.0 BPM
```

This is the most common source of bugs when implementing VirtualDJ support. ConaConverter unit-tests this conversion explicitly.

### Key notation

VirtualDJ uses its own key notation (e.g. `"8m"` for 8 minor, `"11A"` for Camelot 11A). Keys are preserved as-is; no cross-notation mapping is performed in the current version.

### References

- [Mixxx: VirtualDJ Cue Storage Format](https://github.com/mixxxdj/mixxx/wiki/Virtual-Dj-Cue-Storage-Format)

---

## Cross-format compatibility notes

### Cue slot mapping

| Concept | Rekordbox | Serato | Engine OS | VirtualDJ |
|---|---|---|---|---|
| Hot cue slots | 0–8 (Num attr) | 0–7 | 0–7 (slot index) | 0–7 (Num attr) |
| Memory cue | Num = -1 | Separate type | Not supported | `automix` type |
| Loop | Type = 4 | Loop type | Separate column | Type = `loop` |

### Color encoding

| Platform | Format |
|---|---|
| Rekordbox | Separate Red, Green, Blue int attributes (0–255) |
| Engine OS | 0x00RRGGBB packed uint32 in BLOB |
| VirtualDJ | `#RRGGBB` hex string |
| Serato | Packed int in GEOB tag |

ConaConverter normalises all colors to a single `0xRRGGBB` integer in the universal model.

### Position units

| Platform | Unit | Conversion |
|---|---|---|
| Rekordbox | Seconds (float string) | Direct |
| Serato Markers2 | Milliseconds | `÷ 1000` |
| Serato BeatGrid | Samples | `÷ sample_rate` |
| Engine OS quickCues | Milliseconds | `÷ 1000` |
| Engine OS beatGrid | Samples | `÷ sample_rate` |
| VirtualDJ | Seconds | Direct |

### File path portability

Track file paths are stored as absolute paths in every format. If a DJ's music is on an external drive with a different drive letter or mount point between machines, the target software will need to relocate tracks after import. ConaConverter preserves paths exactly as they appear in the source — path remapping is outside scope.
