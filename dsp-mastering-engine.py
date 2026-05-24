"""
DSP Mastering Engine: Professional Audio Processing Pipeline
Komponenten:
  1. K-Weighting LUFS-Messung (ITU-R BS.1770-4)
  2. Multiband-Kompression & Lookahead-Limiting
  3. 3D-Binaural Spatialization (HRTF)
  4. Haptische Sub-Bass-Extraktion
  5. Mastering-Pipeline
"""

import numpy as np
from scipy.signal import lfilter, firwin, fftconvolve, butter
from typing import Tuple
import json

class DSPMasteringEngine:
    """Professionelle Mastering-Engine mit K-Weighting und True-Peak Limiting"""
    
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        
        # K-Weighting Filter Koeffizienten (Stufe 1: High-Shelving @2kHz)
        self.b1 = [1.53512485958697, -2.69169618940638, 1.19839281083819]
        self.a1 = [1.0, -1.69065929318241, 0.73248077421585]
        
        # K-Weighting Filter Koeffizienten (Stufe 2: RLB Hochpass @75Hz)
        self.b2 = [1.0, -2.0, 1.0]
        self.a2 = [1.0, -1.99004745483398, 0.99007225036621]
        
        # State für Butterworth Filter (Multiband)
        self.create_multiband_filters()
        
    def create_multiband_filters(self):
        """Erstellt 3-Band Multiband-Kompression (Bass, Mid, High)"""
        # Bass: 0-200Hz
        self.bass_b, self.bass_a = butter(2, 200 / (self.sr / 2), btype='low')
        
        # Mid: 200-2kHz (Bandpass)
        self.mid_b, self.mid_a = butter(2, [200 / (self.sr / 2), 2000 / (self.sr / 2)], btype='band')
        
        # High: 2kHz+
        self.high_b, self.high_a = butter(2, 2000 / (self.sr / 2), btype='high')
        
    def apply_k_weighting(self, signal: np.ndarray) -> np.ndarray:
        """
        Wendet K-Weighting nach ITU-R BS.1770-4 an.
        Simuliert die menschliche Hörkurve.
        
        Mathematik:
        y1[n] = b0*x[n] + b1*x[n-1] + b2*x[n-2] - a1*y1[n-1] - a2*y1[n-2]
        y2[n] = b0*y1[n] + b1*y1[n-1] + b2*y1[n-2] - a1*y2[n-1] - a2*y2[n-2]
        
        Args:
            signal: Shape (N_samples, 2) für Stereo
            
        Returns:
            K-gewichtetes Signal
        """
        out = np.zeros_like(signal)
        for ch in range(signal.shape[1]):
            s1 = lfilter(self.b1, self.a1, signal[:, ch])
            out[:, ch] = lfilter(self.b2, self.a2, s1)
        return out
    
    def calculate_lufs(self, signal: np.ndarray, block_size: int = 2048) -> float:
        """
        Berechnet LUFS (Loudness Units relative to Full Scale).
        
        Formel: L_K = -0.691 + 10*log10(Σ G_i * ψ_i)
        wobei ψ_i = (1/N) * Σ y_i[n]^2
        
        Args:
            signal: Stereo-Audio (N, 2)
            block_size: Integrations-Fenster in Samples
            
        Returns:
            LUFS-Wert (float)
        """
        if len(signal) < block_size:
            signal = np.pad(signal, ((0, block_size - len(signal)), (0, 0)))
        
        # K-Weighting anwenden
        weighted = self.apply_k_weighting(signal)
        
        # Energieberechnung pro Kanal
        n_blocks = len(weighted) // block_size
        energies = []
        
        for b in range(n_blocks):
            start = b * block_size
            end = start + block_size
            block = weighted[start:end]
            
            # Quadratische Energie pro Kanal
            energy_left = np.mean(block[:, 0] ** 2)
            energy_right = np.mean(block[:, 1] ** 2)
            
            # Gewichtung (L: 1.0, R: 1.0)
            total_energy = energy_left + energy_right
            energies.append(total_energy)
        
        # Mittlere Energie über alle Blöcke
        mean_energy = np.mean(energies)
        
        if mean_energy < 1e-12:
            return -np.inf
        
        lufs = -0.691 + 10 * np.log10(mean_energy)
        return lufs
    
    def lookahead_limiter(
        self, 
        signal: np.ndarray, 
        threshold_db: float = -16.0, 
        ceiling_db: float = -0.2, 
        lookahead_ms: float = 5.0,
        release_time_ms: float = 200.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        True-Peak Lookahead Limiter mit Gain-Reduction-Kurve.
        Verhindert digitales Clipping bei maximaler Lautstärken-Erhöhung.
        
        Logik:
        1. Envelope-Detection: max(|L|, |R|) pro Fenster
        2. Lookahead: Schaut 5ms in die Zukunft
        3. Gain-Reduktion: Wenn Pegel > threshold, reduziere Gain proportional
        4. Release: Exponentielles Entspannen der Gain-Kurve
        
        Args:
            signal: Input-Audio (N, 2)
            threshold_db: Kompressions-Threshold (-16 ist typisch)
            ceiling_db: Maximaler Output-Pegel (-0.2 für Sicherheit)
            lookahead_ms: Vorausschau-Zeit
            release_time_ms: Entspannungs-Zeit nach Limiting
            
        Returns:
            (output_signal, gain_reduction_curve)
        """
        n_samples = len(signal)
        lookahead_samples = int((lookahead_ms / 1000.0) * self.sr)
        release_samples = int((release_time_ms / 1000.0) * self.sr)
        
        threshold_linear = 10 ** (threshold_db / 20.0)
        ceiling_linear = 10 ** (ceiling_db / 20.0)
        
        # 1. Envelope-Detection (Max pro Fenster)
        envelope = np.zeros(n_samples)
        for n in range(n_samples):
            envelope[n] = np.max(np.abs(signal[n, :]))
        
        # 2. Lookahead & Peak-Detection
        gain_reduction = np.ones(n_samples)
        
        for n in range(n_samples):
            lookahead_end = min(n + lookahead_samples, n_samples)
            local_peak = np.max(envelope[n:lookahead_end])
            
            if local_peak > threshold_linear:
                target_gain = threshold_linear / local_peak
            else:
                target_gain = 1.0
            
            # Smoothing mit Release-Zeit (exponentiell)
            if n == 0:
                gain_reduction[n] = target_gain
            else:
                alpha = 1.0 / (release_samples + 1)
                gain_reduction[n] = alpha * target_gain + (1 - alpha) * gain_reduction[n-1]
        
        # 3. Makeup-Gain berechnen
        makeup_gain = ceiling_linear / threshold_linear
        
        # 4. Gain anwenden
        output_signal = np.zeros_like(signal)
        for ch in range(signal.shape[1]):
            output_signal[:, ch] = signal[:, ch] * gain_reduction * makeup_gain
        
        return output_signal, gain_reduction
    
    def multiband_compression(
        self, 
        signal: np.ndarray,
        bass_ratio: float = 2.0,
        mid_ratio: float = 1.5,
        high_ratio: float = 1.2,
        threshold_db: float = -20.0
    ) -> np.ndarray:
        """
        3-Band Multiband-Kompression für präzisere Dynamik-Kontrolle.
        
        Trennt Signal in Bass/Mid/High Bands und komprimiert unabhängig.
        Verhindert, dass Bassbeats den gesamten Mix komprimieren.
        
        Args:
            signal: Input-Audio (N, 2)
            bass_ratio: Kompressions-Verhältnis für Bass (>1)
            mid_ratio: Kompressions-Verhältnis für Mids
            high_ratio: Kompressions-Verhältnis für Highs
            threshold_db: Schwelle pro Band
            
        Returns:
            Komprimiertes Signal (N, 2)
        """
        threshold_linear = 10 ** (threshold_db / 20.0)
        
        # Splitten in Frequenzbänder (monoCompressionfilter)
        bass = lfilter(self.bass_b, self.bass_a, signal[:, 0])
        mid = lfilter(self.mid_b, self.mid_a, signal[:, 0])
        high = lfilter(self.high_b, self.high_a, signal[:, 0])
        
        # Kompressions-Funktionen für jedes Band
        def compress_band(band, ratio):
            output = np.zeros_like(band)
            for i, sample in enumerate(band):
                if np.abs(sample) > threshold_linear:
                    # Soft-Knee Kompression
                    gain = (threshold_linear + (np.abs(sample) - threshold_linear) / ratio) / np.abs(sample)
                    output[i] = sample * gain
                else:
                    output[i] = sample
            return output
        
        bass_comp = compress_band(bass, bass_ratio)
        mid_comp = compress_band(mid, mid_ratio)
        high_comp = compress_band(high, high_ratio)
        
        # Rekombination
        output = bass_comp + mid_comp + high_comp
        
        return np.column_stack((output, output))  # Back to Stereo


class Binaural3DEngine:
    """
    3D-Raumklang-Engine mit HRTF-Simulierung und haptischen Effekten.
    Erzeugt psychoakustische 3D-Positionierung über ITD/ILD.
    
    ITD = Interaural Time Difference (Zeitverzögerung zwischen Ohren)
    ILD = Interaural Level Difference (Pegelunterschied durch Kopfabschattung)
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        self.head_radius = 0.0875  # Mittlerer Kopfradius in Metern
        self.sound_speed = 343.0    # Schallgeschwindigkeit in m/s (20°C)
    
    def calculate_itd_ild(self, azimuth_deg: float) -> Tuple[float, Tuple[float, float]]:
        """
        Berechnet ITD (Interaural Time Difference) und ILD (Interaural Level Difference).
        
        ITD-Formel (nach Woodworth & Schlosberg):
        ITD(θ) = (r/c) * (θ + sin(θ))
        
        wobei:
        r = Kopfradius (~0.0875m)
        c = Schallgeschwindigkeit (~343 m/s)
        θ = Azimutwinkel in Radianten
        
        Args:
            azimuth_deg: Azimutwinkel in Grad (-90 = links, 0 = mitte, 90 = rechts)
            
        Returns:
            (itd_seconds, (ild_left, ild_right))
        """
        rad = np.radians(azimuth_deg)
        
        # ITD berechnen (in Sekunden)
        itd = (self.head_radius / self.sound_speed) * (rad + np.sin(rad))
        
        # ILD berechnen (trigonometrische Approximation)
        # Ohr in Richtung der Quelle: Volles Signal (1.0)
        # Ohr gegenüber: Gedämpft durch Kopfabschattung
        ild_left = np.cos(np.clip(rad - np.pi/4, -np.pi/2, np.pi/2))
        ild_right = np.cos(np.clip(rad + np.pi/4, -np.pi/2, np.pi/2))
        
        return itd, (ild_left, ild_right)
    
    def apply_3d_spatialization(
        self, 
        signal: np.ndarray, 
        azimuth_deg: float,
        elevation_deg: float = 0.0
    ) -> np.ndarray:
        """
        Wendet HRTF-basierte 3D-Positionierung an.
        Nutzt ITD (Delay) und ILD (Level-Pegel) für räumliche Positionierung.
        
        Args:
            signal: Stereo-Audio (N, 2)
            azimuth_deg: Horizontaler Winkel (-90 bis 90)
            elevation_deg: Vertikaler Winkel (vereinfacht ignoriert)
            
        Returns:
            Spatialisiertes Signal (N, 2)
        """
        itd, (ild_left, ild_right) = self.calculate_itd_ild(azimuth_deg)
        delay_samples = int(np.abs(itd) * self.sr)
        
        # Pegel anpassen
        left_channel = signal[:, 0] * ild_left
        right_channel = signal[:, 1] * ild_right
        
        # Verzögerung anwenden
        if itd > 0:  # Schall von rechts, linkes Ohr bekommt es später
            left_channel = np.concatenate([np.zeros(delay_samples), left_channel[:-delay_samples]])
        elif itd < 0:  # Schall von links, rechtes Ohr bekommt es später
            right_channel = np.concatenate([np.zeros(delay_samples), right_channel[:-delay_samples]])
        
        return np.column_stack((left_channel, right_channel))
    
    def extract_haptic_sub_bass(
        self, 
        signal: np.ndarray, 
        cutoff_hz: float = 80.0,
        num_taps: int = 101
    ) -> np.ndarray:
        """
        Extrahiert phasenstarres Haptik-Signal für Körperschallwandler/Subwoofer.
        Verwendet FIR-Filter mit linearer Phase zur Phasenkohärenz.
        
        Der menschliche Körper nimmt Frequenzen <80Hz primär über Knochenleitung
        und Vibrationsmechanoreceptoren (Pacinian-Körperchen) wahr.
        
        Args:
            signal: Input-Audio (N, 2)
            cutoff_hz: Cutoff-Frequenz für Tiefpass
            num_taps: FIR-Filterlänge (muss ungerade sein für lineare Phase)
            
        Returns:
            Mono Haptic-Signal (N,) für Vibrationsmotoren
        """
        # Symmetrischer FIR-Tiefpass-Filter (Hamming-Fenster)
        fir_coeff = firwin(num_taps, cutoff_hz / (0.5 * self.sr), window='hamming')
        
        # Mono-Downmix
        mono_signal = np.mean(signal, axis=1)
        
        # Schnelle FFT-Konvolution
        haptic_channel = fftconvolve(mono_signal, fir_coeff, mode='same')
        
        # Soft-Clipping (tanh Sättigung) für "fühlbare" Harmoniken
        # tanh erzeugt sanfte Übersteuerung, die Subharmoniken erzeugt
        haptic_saturated = np.tanh(haptic_channel * 1.5)
        
        return haptic_saturated


class AIAudioMixingPipeline:
    """
    Hybrid AI-DJ Pipeline: Curation → Transition → Mastering → 3D Spatialization
    Kombiniert alle DSP-Komponenten in einen nahtlosen Workflow.
    """
    
    def __init__(self, sample_rate: int = 44100):
        self.sr = sample_rate
        self.mastering = DSPMasteringEngine(sample_rate)
        self.spatialization = Binaural3DEngine(sample_rate)
        self.analytics = {}
    
    def analyze_track(self, signal: np.ndarray) -> dict:
        """
        Analysiert Audio-Track auf Mixing-relevante Parameter.
        
        Returns:
            Dictionary mit BPM, Energie, Spectral-Centroid, etc.
        """
        # RMS-Energie
        rms = np.sqrt(np.mean(signal ** 2))
        rms_db = 20 * np.log10(rms + 1e-10)
        
        # Peak-Level
        peak = np.max(np.abs(signal))
        peak_db = 20 * np.log10(peak + 1e-10)
        
        # Spektrales Centroid (vereinfacht: häufigste Frequenz)
        fft = np.fft.fft(signal[:, 0])
        freqs = np.fft.fftfreq(len(signal), 1/self.sr)
        spectral_centroid = np.abs(freqs[np.argmax(np.abs(fft))])
        
        # Dynamik-Range
        dynamic_range = peak_db - rms_db
        
        return {
            "rms_db": rms_db,
            "peak_db": peak_db,
            "dynamic_range_db": dynamic_range,
            "spectral_centroid_hz": spectral_centroid,
            "lufs": self.mastering.calculate_lufs(signal),
            "duration_seconds": len(signal) / self.sr
        }
    
    def process_mix(
        self,
        signal: np.ndarray,
        target_lufs: float = -14.0,
        azimuth_deg: float = 0.0,
        add_haptics: bool = True
    ) -> dict:
        """
        Vollständige Mix-Verarbeitung mit allen DSP-Stufen.
        
        Args:
            signal: Raw Audio (N, 2)
            target_lufs: Ziel-Lautstärke (Spotify: -14 LUFS, YouTube: -14 LUFS)
            azimuth_deg: 3D-Position (für Spatialization)
            add_haptics: Haptik-Signal extrahieren?
            
        Returns:
            Dictionary mit verarbeitetem Audio und Metadaten
        """
        print(f"🎛️ Processing audio pipeline...")
        
        # 1. Analyse
        pre_analysis = self.analyze_track(signal)
        lufs_pre = pre_analysis["lufs"]
        print(f"  └─ Pre-Analysis: LUFS={lufs_pre:.2f}, Peak={pre_analysis['peak_db']:.2f}dB")
        
        # 2. 3D Spatialization
        spatialized = self.spatialization.apply_3d_spatialization(
            signal, 
            azimuth_deg=azimuth_deg
        )
        print(f"  └─ 3D Spatialization: azimuth={azimuth_deg}°")
        
        # 3. Multiband Compression
        multiband = self.mastering.multiband_compression(spatialized)
        print(f"  └─ Multiband Compression applied")
        
        # 4. Lookahead Limiting (zum Ziel-LUFS)
        gain_needed_db = target_lufs - lufs_pre
        threshold_db = -16.0 - gain_needed_db / 2
        
        limited, gain_reduction = self.mastering.lookahead_limiter(
            multiband,
            threshold_db=threshold_db,
            ceiling_db=-0.1,
            lookahead_ms=5.0
        )
        print(f"  └─ Lookahead Limiting: threshold={threshold_db:.1f}dB")
        
        # 5. Post-Analyse
        post_analysis = self.analyze_track(limited)
        lufs_post = post_analysis["lufs"]
        print(f"  └─ Post-Analysis: LUFS={lufs_post:.2f}, Peak={post_analysis['peak_db']:.2f}dB")
        
        # 6. Haptik-Extraktion
        haptic_signal = None
        if add_haptics:
            haptic_signal = self.spatialization.extract_haptic_sub_bass(
                limited,
                cutoff_hz=80.0
            )
            print(f"  └─ Haptic Sub-Bass extracted (<80Hz)")
        
        return {
            "audio_processed": limited,
            "haptic_signal": haptic_signal,
            "pre_analysis": pre_analysis,
            "post_analysis": post_analysis,
            "gain_reduction_curve": gain_reduction,
            "target_lufs": target_lufs,
            "achieved_lufs": lufs_post,
            "lufs_delta": lufs_post - target_lufs,
            "azimuth_deg": azimuth_deg
        }


# ============================================================================
# DEMO & TESTING
# ============================================================================

def generate_test_signal(duration_sec: float = 3.0, sr: int = 44100) -> np.ndarray:
    """Generiert ein Test-Audio-Signal (Drums + Bass)"""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    
    # Kick Drum (Sub-Bass)
    kick_freq = 60
    kick_envelope = np.exp(-4 * (t % 0.5))
    kick = np.sin(2 * np.pi * kick_freq * t) * kick_envelope
    
    # Snare (Transient)
    snare_noise = np.random.normal(0, 0.15, len(t))
    snare_envelope = np.exp(-15 * ((t + 0.125) % 0.5))
    snare = snare_noise * snare_envelope
    
    # HiHat (Bright Click)
    hihat_freq = 8000
    hihat_envelope = np.exp(-20 * ((t + 0.25) % 0.5))
    hihat = np.sin(2 * np.pi * hihat_freq * t) * hihat_envelope
    
    # Combine
    mono = kick + snare * 0.5 + hihat * 0.3
    mono = np.clip(mono, -1, 1) * 0.8
    
    return np.column_stack((mono, mono))  # Stereo


if __name__ == "__main__":
    print("=" * 70)
    print("🎛️ AI-DJ Mastering Engine - Demonstration")
    print("=" * 70)
    
    # Generate test audio
    print("\n📊 Generating test signal (3 seconds of Drum Pattern)...")
    test_audio = generate_test_signal(duration_sec=3.0, sr=44100)
    
    # Initialize Pipeline
    pipeline = AIAudioMixingPipeline(sample_rate=44100)
    
    # Process with different azimuth angles (3D movement simulation)
    azimuths = [0.0, 45.0, -45.0, 90.0]
    
    for azimuth in azimuths:
        print(f"\n{'='*70}")
        print(f"🎧 Processing with Azimuth = {azimuth}°")
        print(f"{'='*70}")
        
        result = pipeline.process_mix(
            test_audio,
            target_lufs=-14.0,
            azimuth_deg=azimuth,
            add_haptics=True
        )
        
        print(f"\n✅ Result Summary:")
        print(f"   Target LUFS: {result['target_lufs']}")
        print(f"   Achieved LUFS: {result['achieved_lufs']:.2f}")
        print(f"   Delta: {result['lufs_delta']:+.2f} dB")
        print(f"   Pre-Peak: {result['pre_analysis']['peak_db']:.2f}dB")
        print(f"   Post-Peak: {result['post_analysis']['peak_db']:.2f}dB")
        print(f"   Haptic Signal Generated: {result['haptic_signal'] is not None}")
    
    print(f"\n{'='*70}")
    print("✨ Processing Complete!")
    print(f"{'='*70}\n")
