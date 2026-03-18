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

## Traktor (Native Instruments)

### File used

**`collection.nml`** — Traktor's main library file, exported via _File > Export Collection_.

Default location:

| OS | Location |
|---|---|
| Windows | `C:\Users\{name}\Documents\Native Instruments\Traktor Pro 3\` |
| macOS | `~/Documents/Native Instruments/Traktor Pro 3/` |

### XML structure

```xml
<NML VERSION="23">
  <HEAD COMPANY="www.native-instruments.com" PROGRAM="Traktor"/>
  <COLLECTION ENTRIES="N">
    <ENTRY TITLE="Track Title" ARTIST="Artist Name" AUDIO_ID="..." MODIFIED_DATE="2024/1/1">
      <LOCATION DIR="/:Users/:name/:Music/:" FILE="track.mp3" VOLUME="C:" VOLUMEID="C:"/>
      <ALBUM TRACK="0" TITLE="Album Name"/>
      <INFO BITRATE="320000" GENRE="Techno" COMMENT="" KEY="8m"
            PLAYTIME="240" PLAYTIME_FLOAT="240.000"/>
      <TEMPO BPM="128.000000" BPM_QUALITY="100"/>
      <CUE_V2 NAME="Intro" DISPL_ORDER="0" TYPE="0" START="4123.000000"
              LEN="0.000000" REPEATS="-1" HOTCUE="0"/>
    </ENTRY>
  </COLLECTION>
  <PLAYLISTS>
    <NODE TYPE="FOLDER" NAME="$ROOT" COUNT="1">
      <SUBNODES COUNT="1">
        <NODE TYPE="PLAYLIST" NAME="My Playlist">
          <PLAYLIST ENTRIES="1" TYPE="LIST" UUID="...">
            <ENTRY>
              <PRIMARYKEY TYPE="TRACK" KEY="C:/Users/name/Music/track.mp3"/>
            </ENTRY>
          </PLAYLIST>
        </NODE>
      </SUBNODES>
    </NODE>
  </PLAYLISTS>
</NML>
```

### CUE_V2 attributes

| Attribute | Description |
|---|---|
| `TYPE` | `0` = cue, `1` = fade-in, `2` = fade-out, `3` = load, `4` = **grid marker**, `5` = loop |
| `HOTCUE` | `-1` = not a hot cue (memory cue); `0–7` = hot cue slot index |
| `START` | Position in **milliseconds** (float string) |
| `LEN` | Length in milliseconds for loops; `0` for all other types |
| `NAME` | Label string |
| `DISPL_ORDER` | Display order in Traktor's cue list |
| `REPEATS` | Loop repeat count; `-1` = infinite |

> **Note:** Traktor does not store cue colors in the NML format. Colors set in Traktor are not exported and will not survive a round-trip through ConaConverter.

### Beat grid

Beat grid markers are stored as `CUE_V2` elements with `TYPE="4"`. The `START` attribute gives the position of the beat anchor in milliseconds. The BPM comes from the `<TEMPO BPM="..."/>` element on the same `ENTRY`.

ConaConverter reads all TYPE=4 elements as `BeatGridMarker` objects and writes them back as TYPE=4 elements. They are kept strictly separate from cue points.

### LOCATION path encoding

Traktor uses a non-standard path encoding where each directory component is prefixed with `/:`:

```
/Users/john/Music/  →  /:Users/:john/:Music/:
```

On Windows, the drive letter is stored separately in the `VOLUME` attribute:
```
VOLUME="C:"  DIR="/:Users/:john/:Music/:"  FILE="track.mp3"
→ C:/Users/john/Music/track.mp3
```

On macOS, `VOLUME` holds the volume name (e.g. `"Macintosh HD"`), but the path is reconstructed by decoding the `DIR` attribute directly (which already starts with `/`).

The `PRIMARYKEY KEY` attribute in the `PLAYLISTS` section uses the standard decoded path (no `/:` encoding) as the track lookup key.

### References

- [traktor-nml-utils Python library](https://github.com/wolkenarchitekt/traktor-nml-utils)
- [Mixxx NML format notes](https://github.com/mixxxdj/mixxx/wiki/Traktor-Library-Format)

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
