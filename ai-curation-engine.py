"""
AI-Curation & Transition Alignment Engine
Komponenten:
  1. Playlist-Curation basierend auf MFCC-Ähnlichkeit
  2. BPM & Harmonic Key Detection
  3. Automatisierte Phrase-Alignment für Übergänge
  4. Energy-Level Optimization für Sets
"""

import numpy as np
from typing import List, Dict, Tuple
import librosa
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans


class AudioFeatureExtractor:
    """Extrahiert Mixing-relevante Audio-Features aus Tracks"""
    
    def __init__(self, sr: int = 22050):
        self.sr = sr
        self.scaler = StandardScaler()
    
    def extract_mfcc(self, y: np.ndarray, n_mfcc: int = 13) -> np.ndarray:
        """
        Mel-Frequency Cepstral Coefficients für akustische Ähnlichkeit.
        MFCCs bilden die Spektral-Charakteristiken ab, die das menschliche Gehör wahrnimmt.
        
        Args:
            y: Audio-Zeitreihe
            n_mfcc: Anzahl der MFCC-Koeffizienten
            
        Returns:
            MFCC-Feature (n_mfcc, T)
        """
        return librosa.feature.mfcc(y=y, sr=self.sr, n_mfcc=n_mfcc)
    
    def extract_chroma(self, y: np.ndarray) -> np.ndarray:
        """
        Chroma-Features für harmonische Kompatibilität (12-Ton-System).
        Zeigt, welche Musik-Tonarten in einem Track dominieren.
        
        Returns:
            Chroma-Feature (12, T)
        """
        return librosa.feature.chroma_cqt(y=y, sr=self.sr)
    
    def extract_tempogram(self, y: np.ndarray) -> Tuple[float, np.ndarray]:
        """
        Detektiert BPM und Tempo-Stabilität mittels Onset-Detektion.
        
        Returns:
            (bpm, onset_frames)
        """
        # Onset-Detektion
        onset_env = librosa.onset.onset_strength(y=y, sr=self.sr)
        
        # Tempogram
        tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=self.sr)
        
        # BPM-Schätzung
        bpm = librosa.beat.tempo(onset_envelope=onset_env, sr=self.sr)[0]
        
        # Downbeats (Strong Beats)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env)
        
        return float(bpm), onset_frames
    
    def extract_spectral_centroid(self, y: np.ndarray) -> np.ndarray:
        """
        Spektrales Centroid: durchschnittliche Frequenz im Spektrum.
        Charakterisiert, ob ein Track "dunkel" oder "hell" klingt.
        
        Returns:
            Spectral Centroid über Zeit (T,)
        """
        return librosa.feature.spectral_centroid(y=y, sr=self.sr)[0]
    
    def extract_energy_contour(self, y: np.ndarray, frame_length: int = 2048) -> np.ndarray:
        """
        Energie-Hüllkurve zur Bestimmung des Energy Levels (1-10 Skala).
        
        Returns:
            RMS-Energie über Zeit (T,)
        """
        S = np.abs(librosa.stft(y, n_fft=frame_length))
        energy = librosa.feature.rms(S=S)[0]
        return energy
    
    def compute_track_signature(self, y: np.ndarray) -> Dict:
        """
        Berechnet einen umfassenden Track-"Fingerprint" für KI-Matching.
        
        Args:
            y: Audio-Zeitreihe
            
        Returns:
            Dictionary mit allen Features
        """
        mfcc = self.extract_mfcc(y)
        chroma = self.extract_chroma(y)
        bpm, onsets = self.extract_tempogram(y)
        spectral_centroid = self.extract_spectral_centroid(y)
        energy = self.extract_energy_contour(y)
        
        # Metriken aggregieren
        mfcc_mean = np.mean(mfcc, axis=1)
        mfcc_std = np.std(mfcc, axis=1)
        chroma_mean = np.mean(chroma, axis=1)
        
        # Energy Level auf 1-10 Skala normalisieren
        energy_norm = (energy - np.min(energy)) / (np.max(energy) - np.min(energy) + 1e-10)
        energy_level = 1 + 9 * np.mean(energy_norm)
        
        # Spectral Brightness (0-1)
        brightness = np.mean(spectral_centroid) / (self.sr / 2)
        
        return {
            "bpm": bpm,
            "energy_level": energy_level,
            "brightness": brightness,
            "mfcc_mean": mfcc_mean,
            "mfcc_std": mfcc_std,
            "chroma_mean": chroma_mean,
            "spectral_centroid": np.mean(spectral_centroid),
            "onsets": onsets,
            "duration_frames": len(y)
        }


class HarmonicMixingAnalyzer:
    """
    Bestimmt harmonische Kompatibilität nach dem Camelot Wheel System.
    Erlaubt "Harmonic Mixing" = Übergänge ohne tonale Konflikte.
    """
    
    # Camelot Wheel Mapping (Musik-Tonarten zu Winkeln)
    # 12-Ton System: C, G, D, A, E, B, F#, C#, G#, D#, A#, F
    CAMELOT_MAJOR = {
        0: "8B",   # C Major
        7: "8B",   # G Major
        2: "9B",   # D Major
        9: "9B",   # A Major
        4: "10B",  # E Major
        11: "10B", # B Major
        6: "11B",  # F# Major
        1: "12B",  # C# Major
        8: "1B",   # G# Major
        3: "2B",   # D# Major
        10: "3B",  # A# Major
        5: "4B"    # F Major
    }
    
    CAMELOT_MINOR = {
        0: "5A",   # A Minor (relative zu C Major)
        7: "12A",  # E Minor
        2: "1A",   # B Minor
        9: "2A",   # F# Minor
        4: "3A",   # C# Minor
        11: "4A",  # G# Minor
        6: "5A",   # D# Minor
        1: "6A",   # A# Minor
        8: "7A",   # F Minor
        3: "8A",   # C Minor
        10: "9A",  # G Minor
        5: "10A"   # D Minor
    }
    
    @staticmethod
    def chroma_to_key(chroma: np.ndarray) -> Tuple[int, str]:
        """
        Bestimmt die Tonart aus Chroma-Features.
        
        Args:
            chroma: Shape (12,) oder (12, T)
            
        Returns:
            (chromatic_number, mode) wobei mode in ["Major", "Minor"]
        """
        # Chroma aggregieren falls zeitlich
        if chroma.ndim > 1:
            chroma_mean = np.mean(chroma, axis=1)
        else:
            chroma_mean = chroma
        
        # Die dominanteste Note
        root_note = np.argmax(chroma_mean)
        
        # Vereinfachte Mode-Detection: Minor hat stärkere kleine Terz (3 Halbtöne)
        third_degree = chroma_mean[(root_note + 3) % 12]
        minor_third = chroma_mean[(root_note + 2) % 12]
        
        mode = "Minor" if minor_third > third_degree else "Major"
        
        return root_note, mode
    
    @classmethod
    def get_camelot_position(cls, root_note: int, mode: str) -> str:
        """
        Gibt die Camelot-Wheel-Position an.
        
        Returns:
            String wie "8B" oder "5A"
        """
        wheel_map = cls.CAMELOT_MAJOR if mode == "Major" else cls.CAMELOT_MINOR
        return wheel_map.get(root_note, "?")
    
    @staticmethod
    def camelot_distance(pos1: str, pos2: str) -> int:
        """
        Berechnet die harmonische Distanz auf dem Camelot Wheel.
        Abstände: +1/-1 = perfekt kompatibel, +/- 7 = stark dissonant.
        
        Args:
            pos1, pos2: Camelot-Positionen wie "8B"
            
        Returns:
            Abstand (0 = gleich, 1 = ideal, 6+ = vermeiden)
        """
        # Vereinfachte Berechnung: nur numerischer Abstand
        num1 = int(pos1[:-1])
        num2 = int(pos2[:-1])
        
        # Zirkular, also min(|diff|, 12-|diff|)
        diff = abs(num1 - num2)
        return min(diff, 12 - diff)


class TransitionAlignmentEngine:
    """
    Automatisiert die Ausrichtung von Übergängen auf Musik-Phrasen.
    Mischt Tracks exakt auf Bars/Beats aus, um Störungen zu vermeiden.
    """
    
    def __init__(self, sr: int = 22050):
        self.sr = sr
        self.feature_extractor = AudioFeatureExtractor(sr)
    
    def detect_phrase_boundaries(
        self, 
        y: np.ndarray, 
        bpm: float
    ) -> List[int]:
        """
        Detektiert Phrase-Grenzen (8, 16, 32 Bar Blöcke).
        Nutzt Onset-Detektion und Energy-Spitzen.
        
        Args:
            y: Audio
            bpm: Track BPM
            
        Returns:
            Liste von Sample-Indizes (Phrase-Anfänge)
        """
        # Onset-Detektion
        onset_env = librosa.onset.onset_strength(y=y, sr=self.sr)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env)
        
        # In Samples konvertieren
        onset_samples = librosa.frames_to_samples(onset_frames)
        
        # Beats pro Minute zu Samples umrechnen
        samples_per_beat = (60.0 / bpm) * self.sr
        
        # Phrase-Länge: Typisch 8 Bars = 8*4 Beats (im 4/4 Takt)
        samples_per_phrase = 32 * samples_per_beat
        
        # Phrase-Grenzen extrahieren
        phrase_boundaries = []
        for i, onset in enumerate(onset_samples):
            if i == 0 or onset > phrase_boundaries[-1] + samples_per_phrase * 0.8:
                phrase_boundaries.append(int(onset))
        
        return phrase_boundaries
    
    def calculate_transition_window(
        self,
        track_a_bpm: float,
        track_b_bpm: float,
        duration_sec: float = 32.0
    ) -> Dict:
        """
        Berechnet ein optimales Übergangsfenster.
        
        Args:
            track_a_bpm: Tempo von Track A
            track_b_bpm: Tempo von Track B
            duration_sec: Länge des Übergangsfensters in Sekunden
            
        Returns:
            Dictionary mit Timing-Info
        """
        # Beatgrid ausrichten
        beat_duration_a = 60.0 / track_a_bpm
        beat_duration_b = 60.0 / track_b_bpm
        
        # Übergangsdauer in Beats
        transition_beats = duration_sec / beat_duration_a
        
        # In Bars umrechnen (4 Beats pro Bar im 4/4)
        transition_bars = transition_beats / 4.0
        
        # Feedback
        return {
            "transition_duration_sec": duration_sec,
            "transition_bars": transition_bars,
            "beat_duration_a_ms": beat_duration_a * 1000,
            "beat_duration_b_ms": beat_duration_b * 1000,
            "tempo_delta_bpm": abs(track_a_bpm - track_b_bpm),
            "crossfade_type": "linear" if abs(track_a_bpm - track_b_bpm) < 5 else "exponential"
        }
    
    def optimize_cue_point(
        self,
        y: np.ndarray,
        bpm: float,
        target_bar: int = 1
    ) -> int:
        """
        Findet die beste Cue-Point für Track-Start auf exaktem Beat/Bar.
        
        Args:
            y: Audio
            bpm: BPM
            target_bar: Ziel-Bar (1-basiert)
            
        Returns:
            Sample-Index für optimalen Start
        """
        # Onset-Detektion
        onset_env = librosa.onset.onset_strength(y=y, sr=self.sr)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env)
        onset_samples = librosa.frames_to_samples(onset_frames)
        
        # Samples pro Bar
        samples_per_beat = (60.0 / bpm) * self.sr
        samples_per_bar = 4 * samples_per_beat
        
        # Zielposition
        target_sample = target_bar * samples_per_bar
        
        # Nächster Onset zur Zielposition
        best_onset = min(onset_samples, key=lambda x: abs(x - target_sample))
        
        return int(best_onset)


class AIPlaylistCurator:
    """
    KI-gestützte Playlist-Generierung und Set-Optimierung.
    Nutzt semantische Ähnlichkeit + Harmonic Mixing + Energy Curves.
    """
    
    def __init__(self, sr: int = 22050):
        self.sr = sr
        self.feature_extractor = AudioFeatureExtractor(sr)
        self.harmonics = HarmonicMixingAnalyzer()
        self.transitions = TransitionAlignmentEngine(sr)
    
    def rank_compatible_tracks(
        self,
        current_track_sig: Dict,
        candidate_sigs: List[Dict],
        current_key: Tuple[int, str],
        weights: Dict = None
    ) -> List[Tuple[int, float]]:
        """
        Ranked-Liste von Tracks sortiert nach Kompatibilität.
        Nutzt MFCC-Ähnlichkeit + Harmonic Mixing + Energy Flow.
        
        Args:
            current_track_sig: Feature-Signatur des aktuellen Tracks
            candidate_sigs: Liste von Kandidaten-Signaturen
            current_key: (root_note, mode) des aktuellen Tracks
            weights: Gewichtung der Kriterien
            
        Returns:
            Liste von (track_idx, compatibility_score)
        """
        if weights is None:
            weights = {
                "mfcc_similarity": 0.3,
                "harmonic_compatibility": 0.3,
                "energy_flow": 0.2,
                "bpm_delta": 0.2
            }
        
        scores = []
        
        for idx, cand_sig in enumerate(candidate_sigs):
            # 1. MFCC-Ähnlichkeit (akustische Ähnlichkeit)
            mfcc_dist = np.linalg.norm(
                current_track_sig["mfcc_mean"] - cand_sig["mfcc_mean"]
            )
            mfcc_sim = 1.0 / (1.0 + mfcc_dist)
            
            # 2. Harmonische Kompatibilität (Camelot Distance)
            # Benötigt Chroma-Features für Kandidaten (vereinfacht)
            harmonic_compat = 0.5  # Placeholder
            
            # 3. Energy Flow (sollte ähnlich oder steigend sein)
            energy_current = current_track_sig["energy_level"]
            energy_cand = cand_sig["energy_level"]
            energy_flow = 1.0 - abs(energy_current - energy_cand) / 10.0
            
            # 4. BPM-Delta (sollte klein sein)
            bpm_delta = abs(current_track_sig["bpm"] - cand_sig["bpm"])
            bpm_compat = 1.0 / (1.0 + bpm_delta / 10.0)
            
            # Gewichtete Score
            score = (
                weights["mfcc_similarity"] * mfcc_sim +
                weights["harmonic_compatibility"] * harmonic_compat +
                weights["energy_flow"] * energy_flow +
                weights["bpm_delta"] * bpm_compat
            )
            
            scores.append((idx, score))
        
        return sorted(scores, key=lambda x: x[1], reverse=True)
    
    def generate_dj_set(
        self,
        track_sigs: List[Dict],
        target_duration_min: float = 60.0,
        energy_profile: str = "peak"
    ) -> List[int]:
        """
        Generiert eine optimale DJ-Set-Reihenfolge.
        
        Args:
            track_sigs: Liste von Track-Signaturen
            target_duration_min: Zieldauer in Minuten
            energy_profile: "peak" (Spannungsbogen) oder "flat" (konstant)
            
        Returns:
            Track-Indizes in Reihenfolge
        """
        n_tracks = len(track_sigs)
        
        if energy_profile == "peak":
            # Spannungsbogen: Start niedrig -> Peak Mitte -> Outro low
            energy_targets = np.concatenate([
                np.linspace(3, 7, n_tracks // 3),
                np.linspace(7, 10, n_tracks // 3),
                np.linspace(10, 4, n_tracks - 2 * (n_tracks // 3))
            ])
        else:
            # Flach: konstante hohe Energie
            energy_targets = np.ones(n_tracks) * 8.0
        
        # Greedy Selection: Bestes Matching zu Energy-Targets
        used = set()
        playlist = []
        
        for i in range(n_tracks):
            best_idx = -1
            best_score = -1
            
            for idx, sig in enumerate(track_sigs):
                if idx in used:
                    continue
                
                # Score basierend auf Energy-Abstand zum Target
                energy_score = 1.0 - abs(sig["energy_level"] - energy_targets[i]) / 10.0
                
                if energy_score > best_score:
                    best_score = energy_score
                    best_idx = idx
            
            if best_idx >= 0:
                playlist.append(best_idx)
                used.add(best_idx)
        
        return playlist


# ============================================================================
# DEMO
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("🎛️ AI-Curation & Transition Engine - Demonstration")
    print("=" * 70)
    
    # Generate synthetic test tracks
    sr = 22050
    duration = 5.0
    n_test_tracks = 5
    
    print(f"\n📊 Generating {n_test_tracks} test tracks...")
    
    test_tracks = []
    for i in range(n_test_tracks):
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        
        # Each track with different BPM + Frequency characteristics
        bpm = 90 + i * 10
        freq_base = 100 + i * 50
        
        track = (
            0.7 * np.sin(2 * np.pi * freq_base * t) +
            0.3 * np.random.normal(0, 0.1, len(t))
        )
        track = np.clip(track, -1, 1)
        test_tracks.append(track)
    
    # Extract features
    extractor = AudioFeatureExtractor(sr)
    curator = AIPlaylistCurator(sr)
    
    print(f"\n🔍 Extracting features from all tracks...")
    track_sigs = []
    for i, track in enumerate(test_tracks):
        sig = extractor.compute_track_signature(track)
        track_sigs.append(sig)
        print(f"  Track {i}: BPM={sig['bpm']:.1f}, Energy={sig['energy_level']:.1f}/10, "
              f"Brightness={sig['brightness']:.2f}")
    
    # Generate set
    print(f"\n🎵 Generating optimal DJ set (peak energy profile)...")
    playlist = curator.generate_dj_set(
        track_sigs,
        target_duration_min=20.0,
        energy_profile="peak"
    )
    
    print(f"\n✅ Recommended Track Order:")
    for pos, track_idx in enumerate(playlist, 1):
        sig = track_sigs[track_idx]
        print(f"  {pos}. Track {track_idx}: BPM={sig['bpm']:.1f}, "
              f"Energy={sig['energy_level']:.1f}/10")
    
    print(f"\n{'='*70}")
    print("✨ Curation Complete!")
    print(f"{'='*70}\n")
