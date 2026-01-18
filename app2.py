import struct, os, subprocess

PPQN = 480

def write_varlen(value):
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return out

def build_track(events):
    events = sorted(events, key=lambda x: x[0])
    data = bytearray()
    last = 0
    for tick, msg in events:
        delta = tick - last
        last = tick
        data.extend(write_varlen(delta))
        data.extend(msg)
    data.extend(write_varlen(0))
    data.extend([0xFF, 0x2F, 0x00])
    return bytes(data)

# ------------------------------
#   CUTE KPOP SONG SETTINGS
# ------------------------------

bpm = 118  # cute, upbeat tempo
tempo = int(60_000_000 / bpm)
bars = 16
beats = 4
bar_ticks = PPQN * 4

# G Major scale
scale = [55, 57, 59, 60, 62, 64, 66]   # G3 A3 B3 C4 D4 E4 F#4

# Chords: G - Em - C - D
chord_degrees = [
    [0, 2, 4],   # G major
    [5, 0, 2],   # Em
    [3, 5, 0],   # C major
    [4, 6, 1],   # D major
]

# Track 0 (meta)
t0=[]
t0.append((0,[0xFF,0x51,0x03]+list(tempo.to_bytes(3,'big'))))
t0.append((0,[0xFF,0x58,0x04,4,2,24,8]))
t0_data = build_track(t0)

# ------------------------------
#   Chords Track (happy synth)
# ------------------------------

chords=[]
for bar in range(bars):
    degs = chord_degrees[bar % 4]
    st = bar * bar_ticks
    et = st + bar_ticks
    for d in degs:
        note = scale[d]
        chords.append((st, [0x90, note, 90]))
        chords.append((et, [0x80, note, 40]))

t1_data = build_track(chords)

# ------------------------------
#   Cute Pluck Melody
# ------------------------------

melody = []
pattern = [5, 6, 4, 2, 3, 4, 1, 2]   # melodic hop

dur = PPQN // 2  # 8th notes

for bar in range(bars):
    base = bar * bar_ticks
    for i, d in enumerate(pattern):
        st = base + i * dur
        note = scale[d] + 12  # one octave up
        melody.append((st, [0x91, note, 110]))
        melody.append((st + dur, [0x81, note, 50]))

t2_data = build_track(melody)

# ------------------------------
#   Light K-pop Drum Track
# ------------------------------

dr=[]
kick=36
sn=38
hat=42

for bar in range(bars):
    bs = bar * bar_ticks

    # Kick on 1 & 3
    for beat in [0, 2]:
        t = bs + beat * PPQN
        dr.append((t,[0x99,kick,100]))
        dr.append((t+PPQN//4,[0x89,kick,60]))

    # Snare soft on 2 & 4
    for beat in [1, 3]:
        t = bs + beat * PPQN
        dr.append((t,[0x99,sn,70]))
        dr.append((t+PPQN//4,[0x89,sn,40]))

    # Cute hi-hats 8th notes
    for i in range(8):
        t = bs + i*(PPQN//2)
        dr.append((t,[0x99,hat,60]))
        dr.append((t+PPQN//4,[0x89,hat,30]))

t3_data = build_track(dr)

# ------------------------------
#   Write MIDI File
# ------------------------------

header=b"MThd"+struct.pack(">IHHH",6,1,4,PPQN)
tracks=[
    b"MTrk"+struct.pack(">I",len(t0_data))+t0_data,
    b"MTrk"+struct.pack(">I",len(t1_data))+t1_data,
    b"MTrk"+struct.pack(">I",len(t2_data))+t2_data,
    b"MTrk"+struct.pack(">I",len(t3_data))+t3_data,
]

midi_path="cute_kpop.mid"
wav_path="cute_kpop.wav"
mp3_path="cute_kpop.mp3"

with open(midi_path,"wb") as f:
    f.write(header + b"".join(tracks))

print("Saved MIDI:", midi_path)

# ------------------------------
#   MIDI → WAV (FluidSynth)
# ------------------------------

SOUNDFONT_PATH="FluidR3_GM.sf2"   # update if needed

fs_cmd=[
    "fluidsynth",
    "-ni",
    "-F", wav_path,
    "-T", "wav",
    "-r", "44100",
    "-g", "0.9",
    SOUNDFONT_PATH,
    midi_path
]

print("Running FluidSynth...")
subprocess.run(fs_cmd, check=True)
print("Rendered WAV:", wav_path)

# ------------------------------
#   WAV → MP3 (ffmpeg)
# ------------------------------

ff_cmd=[
    "ffmpeg","-y",
    "-i",wav_path,
    "-codec:a","libmp3lame",
    "-b:a","320k",
    mp3_path
]

print("Running ffmpeg...")
subprocess.run(ff_cmd, check=True)
print("Exported MP3:", mp3_path)
