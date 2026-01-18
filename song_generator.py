import struct
import random
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

PPQN = 480 

@dataclass
class SongParams:
    bpm: int = 124
    bars: int = 8
    time_sig_num: int = 4
    time_sig_den: int = 4
    key: str = "C"
    mode: str = "major"
    progression: str = "I-V-vi-IV" # Classic "Axis" progression
    energy: float = 0.75
    swing: float = 0.1
    seed: int = 42
    chord_octave: int = 3
    melody_octave: int = 5
    bass_octave: int = 2

# --- MIDI Low Level Utilities ---
def write_varlen(value: int) -> List[int]:
    # Ensure value is an integer and at least 0
    value = max(0, int(value))
    
    out = [value & 0x7F]
    value >>= 7
    while value > 0: # Use > 0 explicitly
        out.insert(0, (value & 0x7F) | 0x80)
        value >>= 7
    return out

def build_track(events: List[Tuple[int, List[int]]]) -> bytes:
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

# --- Musical Theory Engine ---
NOTE_TO_SEMI = {"C":0,"C#":1,"Db":1,"D":2,"D#":3,"Eb":3,"E":4,"F":5,"F#":6,"Gb":6,"G":7,"G#":8,"Ab":8,"A":9,"A#":10,"Bb":10,"B":11}

def midi_note(note_name: str, octave: int) -> int:
    return 12 * (octave + 1) + NOTE_TO_SEMI[note_name]

def build_scale(root_note: str, mode: str, base_octave: int) -> List[int]:
    root = midi_note(root_note, base_octave)
    # Major vs Natural Minor intervals
    intervals = [0, 2, 4, 5, 7, 9, 11] if mode.lower() == "major" else [0, 2, 3, 5, 7, 8, 10]
    return [root + i for i in intervals]

def roman_to_degree(roman: str) -> int:
    mapping = {"i": 0, "ii": 1, "iii": 2, "iv": 3, "v": 4, "vi": 5, "vii": 6,
               "I": 0, "II": 1, "III": 2, "IV": 3, "V": 4, "VI": 5, "VII": 6}
    return mapping.get(roman.strip().replace("°", ""), 0)

# --- Core Generators ---

def make_chords(params: SongParams, bar_ticks: int):
    rng = random.Random(params.seed)
    scale = build_scale(params.key, params.mode, params.chord_octave)
    tokens = [t.strip() for t in params.progression.replace("|", "-").split("-") if t.strip()]
    
    events, chord_degs_per_bar = [], []
    for bar in range(params.bars):
        root_deg = roman_to_degree(tokens[bar % len(tokens)])
        triad_degs = [root_deg % 7, (root_deg + 2) % 7, (root_deg + 4) % 7]
        chord_degs_per_bar.append(triad_degs)
        
        # OPEN VOICING: Dropping the middle note makes it sound "Professional"
        # Root, 5th (standard), and 3rd (pushed up an octave)
        notes = [
            scale[triad_degs[0]],       # Root
            scale[triad_degs[2]],       # 5th
            scale[triad_degs[1]] + 12   # 3rd (up one octave for "lush" sound)
        ]
        
        st, et = bar * bar_ticks, (bar + 1) * bar_ticks
        for n in notes:
            # Humanize: Real players don't hit all notes at once (Arpeggiation)
            stagger = rng.randint(0, 40) 
            vel = int(65 + 15 * params.energy + rng.randint(-5, 5))
            events.append((st + stagger, [0x90, int(n), vel]))
            events.append((et - 100, [0x80, int(n), 0]))
            
    return events, chord_degs_per_bar

def make_melody(params: SongParams, chord_degs_per_bar: List[List[int]], bar_ticks: int):
    rng = random.Random(params.seed + 123)
    lead_scale = build_scale(params.key, params.mode, params.melody_octave)
    events = []
    
    # Syncopated Rhythm Pattern (16-step grid)
    # This creates a "Call and Response" feel rather than random notes
    rhythm = [1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]

    for bar in range(params.bars):
        base_tick = bar * bar_ticks
        chord_tones = chord_degs_per_bar[bar]
        
        for i, hit in enumerate(rhythm):
            if not hit: continue
            
            # Select note: Priority on chord tones for "Realness"
            if i % 4 == 0 or rng.random() < 0.7:
                deg = rng.choice(chord_tones)
            else:
                deg = rng.choice(range(7))
            
            note = lead_scale[deg]
            
            # Humanization: Micro-timing (not perfectly on the grid)
            shift = rng.randint(-20, 20)
            st = base_tick + (i * (PPQN // 4)) + shift
            
            # Humanization: Velocity accenting
            vel = 100 if i == 0 else (85 if i % 4 == 0 else 70)
            vel += rng.randint(-10, 10)

            duration = (PPQN // 4) + rng.randint(-50, 50)
            events.append((st, [0x91, int(note), int(vel)]))
            events.append((st + duration, [0x81, int(note), 0]))
            
    return events

def make_drums(params: SongParams, bar_ticks: int):
    rng = random.Random(params.seed + 999)
    dr = []
    for bar in range(params.bars):
        bs = bar * bar_ticks
        for i in range(16):
            t = bs + i * (PPQN // 4)
            # Kick on 1 and 3
            if i in [0, 8]:
                dr.append((t, [0x99, 36, 110]))
                dr.append((t + 100, [0x89, 36, 0]))
            # Snare on 4 and 12
            if i in [4, 12]:
                dr.append((t, [0x99, 38, 100]))
                dr.append((t + 100, [0x89, 38, 0]))
            # Hi-Hats with "Groove" (loud-soft-loud-soft)
            if i % 2 == 0:
                vel = 90 if i % 4 == 0 else 65
                dr.append((t, [0x99, 42, vel + rng.randint(-5, 5)]))
                dr.append((t + 60, [0x89, 42, 0]))
    return dr

def generate_song_bytes(params: SongParams) -> bytes:
    bar_ticks = params.time_sig_num * PPQN
    tempo = int(60_000_000 / params.bpm)
    
    # Meta Track
    t0_events = [(0, [0xFF, 0x51, 0x03] + list(tempo.to_bytes(3, "big")))]
    
    chord_ev, chord_degs = make_chords(params, bar_ticks)
    melody_ev = make_melody(params, chord_degs, bar_ticks)
    drum_ev = make_drums(params, bar_ticks)

    tracks = [
        build_track(t0_events),
        build_track(chord_ev),
        build_track(melody_ev),
        build_track(drum_ev)
    ]
    
    header = b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), PPQN)
    chunks = [b"MTrk" + struct.pack(">I", len(t)) + t for t in tracks]
    return header + b"".join(chunks)

def generate_song_bytes_from_dict(d: Dict) -> bytes:
    params = SongParams()
    for k, v in d.items():
        if hasattr(params, k): setattr(params, k, v)
    return generate_song_bytes(params)
