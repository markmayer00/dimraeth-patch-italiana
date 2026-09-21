# -*- coding: utf-8 -*-
"""Chiptune generata al volo, stile intro da keygen. Nessuna dipendenza esterna.

Sintetizza quattro canali (basso a onda quadra, arpeggio pulse, lead con vibrato,
rumore per la batteria), li mixa in un WAV PCM in memoria e lo riproduce in loop
con winsound. Il buffer va tenuto vivo finche suona, altrimenti Windows crasha.
"""
import math, struct, threading
from array import array

SR = 22050          # sample rate: basso di proposito, e' meta' del suono "vecchio"
BPM = 150
BEAT = 60.0 / BPM
STEP = BEAT / 4.0   # sedicesimo

# nome nota -> semitoni sopra il DO centrale
_NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
          "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

def freq(note):
    """'A3' -> frequenza in Hz. None per la pausa."""
    if note is None:
        return 0.0
    name, octv = note[:-1], int(note[-1])
    midi = 12 * (octv + 1) + _NOTES[name]
    return 440.0 * 2 ** ((midi - 69) / 12.0)

# progressione: Am - F - C - G  /  Dm - Am - E - Am
CHORDS = [("A", ["A2", "C4", "E4", "A4"]), ("F", ["F2", "A3", "C4", "F4"]),
          ("C", ["C3", "E4", "G4", "C5"]), ("G", ["G2", "B3", "D4", "G4"]),
          ("D", ["D3", "F4", "A4", "D5"]), ("A", ["A2", "C4", "E4", "A4"]),
          ("E", ["E3", "G#4", "B4", "E5"]), ("A", ["A2", "C4", "E4", "A4"])]
BASS = ["A1", "F1", "C2", "G1", "D2", "A1", "E2", "A1"]
LEAD = [  # una battuta per accordo, ottavi
    ["A4", None, "C5", "B4", "A4", None, "E4", None],
    ["F4", None, "A4", "C5", "A4", None, "F4", None],
    ["G4", None, "E5", "D5", "C5", None, "G4", None],
    ["B4", None, "D5", "G5", "D5", None, "B4", None],
    ["D5", None, "F5", "E5", "D5", None, "A4", None],
    ["C5", None, "E5", "A5", "E5", None, "C5", None],
    ["B4", None, "E5", "G#5", "B5", None, "G#5", None],
    ["A5", None, "E5", "C5", "A4", None, None, None],
]

def _pulse(buf, start, n, f, amp, duty=0.5, decay=0.0, vib=0.0):
    """Onda pulse con decadimento e vibrato opzionali, sommata nel buffer."""
    if f <= 0 or n <= 0:
        return
    phase = 0.0
    for i in range(n):
        if start + i >= len(buf):
            break
        ff = f * (1.0 + vib * math.sin(2 * math.pi * 5.5 * i / SR)) if vib else f
        phase += ff / SR
        if phase >= 1.0:
            phase -= 1.0
        a = amp * (math.exp(-decay * i / SR) if decay else 1.0)
        buf[start + i] += a if phase < duty else -a

_seed = [0x2BAD]
def _rnd():
    """LFSR: il rumore bianco dei chip a 8 bit."""
    s = _seed[0]
    s ^= (s << 7) & 0xFFFF; s ^= s >> 9; s ^= (s << 8) & 0xFFFF
    _seed[0] = s
    return (s & 0xFF) / 127.5 - 1.0

def _noise(buf, start, n, amp, decay):
    for i in range(n):
        if start + i >= len(buf):
            break
        buf[start + i] += amp * _rnd() * math.exp(-decay * i / SR)

def render():
    """Costruisce il loop completo e restituisce i byte di un WAV."""
    bars = len(CHORDS)
    total = int(bars * 4 * BEAT * SR)      # lunghezza esatta del loop
    tail = SR // 2                          # spazio per far decadere le ultime note
    buf = array("f", bytes(4 * (total + tail)))
    spb = int(4 * BEAT * SR)      # campioni per battuta
    sp8 = int(BEAT / 2 * SR)      # ottavo
    sp16 = int(STEP * SR)         # sedicesimo

    for b, (_, chord) in enumerate(CHORDS):
        bar0 = b * spb

        # basso: ottavi sulla fondamentale
        fb = freq(BASS[b])
        for k in range(8):
            _pulse(buf, bar0 + k * sp8, sp8, fb, 0.30, duty=0.5, decay=6.0)

        # arpeggio: sedicesimi che salgono e scendono sulla triade
        seq = chord + chord[::-1][1:3]
        for k in range(16):
            _pulse(buf, bar0 + k * sp16, int(sp16 * 1.1),
                   freq(seq[k % len(seq)]), 0.13, duty=0.125, decay=16.0)

        # lead: melodia a ottavi, pulse stretta con vibrato
        for k, nt in enumerate(LEAD[b]):
            if nt:
                _pulse(buf, bar0 + k * sp8, int(sp8 * 1.6), freq(nt),
                       0.22, duty=0.25, decay=3.2, vib=0.010)

        # batteria: cassa sui quarti dispari, rullante sui pari, charleston sugli ottavi
        for k in range(4):
            at = bar0 + int(k * BEAT * SR)
            if k % 2 == 0:
                _pulse(buf, at, int(0.09 * SR), 60.0, 0.45, duty=0.5, decay=26.0)
            else:
                _noise(buf, at, int(0.10 * SR), 0.22, 30.0)
        for k in range(8):
            _noise(buf, bar0 + k * sp8, int(0.03 * SR), 0.05, 90.0)

    # la coda delle ultime note rientra all'inizio: cosi il loop non ha buchi ne schiocchi
    for i in range(tail):
        buf[i] += buf[total + i]

    # 3 ms di rampa in ingresso: toglie lo scatto sulla giunzione del loop
    ramp = int(0.003 * SR)
    for i in range(ramp):
        buf[i] *= i / ramp

    pcm = array("h", bytes(2 * total))
    for i in range(total):
        v = buf[i] * 0.55                  # sottofondo: presente ma non invadente
        v = 1.0 if v > 1.0 else (-1.0 if v < -1.0 else v)
        pcm[i] = int(v * 30000)

    raw = pcm.tobytes()
    hdr = (b"RIFF" + struct.pack("<I", 36 + len(raw)) + b"WAVEfmt " +
           struct.pack("<IHHIIHH", 16, 1, 1, SR, SR * 2, 2, 16) +
           b"data" + struct.pack("<I", len(raw)))
    return hdr + raw

class Player:
    """Riproduzione in loop.

    winsound rifiuta SND_MEMORY insieme a SND_ASYNC ("Cannot play asynchronously
    from memory"), quindi il WAV va scritto su file temporaneo e riprodotto con
    SND_FILENAME. La sintesi avviene in un thread: la finestra non si blocca.
    """
    def __init__(self, on_error=None):
        self._path = None
        self._on = False
        self._lock = threading.Lock()
        self.on_error = on_error      # callback per far vedere l'errore, invece di nasconderlo

    def _ensure_file(self):
        import os, glob, tempfile
        with self._lock:
            if self._path and os.path.isfile(self._path):
                return self._path
            # ripulisce i residui di sessioni chiuse male; quelli in uso sono bloccati
            for vecchio in glob.glob(os.path.join(tempfile.gettempdir(), "ml2_chiptune_*.wav")):
                try:
                    os.remove(vecchio)
                except OSError:
                    pass
            fd, path = tempfile.mkstemp(prefix="ml2_chiptune_", suffix=".wav")
            with os.fdopen(fd, "wb") as f:
                f.write(render())
            self._path = path
            return path

    def start(self):
        self._on = True
        threading.Thread(target=self._go, daemon=True).start()

    def _go(self):
        try:
            import winsound
            path = self._ensure_file()
            if self._on:
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        except Exception as e:
            if self.on_error:
                self.on_error(e)

    def stop(self):
        self._on = False
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception as e:
            if self.on_error:
                self.on_error(e)

    def cleanup(self):
        """Ferma la musica e cancella il file temporaneo."""
        self.stop()
        import os, time
        if self._path:
            for _ in range(5):                 # Windows puo' tenerlo aperto un istante
                try:
                    os.remove(self._path)
                    break
                except OSError:
                    time.sleep(0.1)
            self._path = None

if __name__ == "__main__":
    import sys, time
    data = render()
    print(f"WAV: {len(data)} byte, {(len(data)-44)/2/SR:.2f} s")
    if "--save" in sys.argv:
        open("chiptune.wav", "wb").write(data)
        print("scritto chiptune.wav")
    if "--play" in sys.argv:
        p = Player(); p.start(); time.sleep(float(sys.argv[-1]) if sys.argv[-1].replace(".","").isdigit() else 10); p.stop()
