/**
 * OMEGA NIO — Terminal-Synth & Arcade Sound Engine
 * Pure Web Audio API synthesis (0 external assets, 0 memory leak, strictly <= 0.6s duration cap).
 * 
 * Supports:
 * 1. TERMINAL_CHIMES (Default): Dezente, elegante Synthesizer-Chimes für 24/7 Hintergrund-Betrieb
 *    - Take-Profit (TP): Harmonisch aufsteigender Major-Pentatonic Tri-Chime
 *    - Stop-Loss (SL): Sanfter, gedämpfter Abwärts-Intervall-Chime
 *    - Ausgeführte Trades & Order-Fills: Kristallklarer Doppel-Glockenton
 *    - RVOL- & Volatilitäts-Anomalien: Subtiler Resonanz-Radar-Chime
 * 2. 8BIT_MEGAMAN: Klassische NES 2A03 Chiptune-Pulse
 * 3. VIRAL_MEME: Kurzprägnante Meme-Sounds
 * 4. HYBRID: Kombination aus Terminal-Chimes und Arcade-Sounds
 */

export type SoundEventType =
  | 'TAKE_PROFIT'
  | 'STOP_LOSS'
  | 'ORDER_FILL'
  | 'SCREENER_ALERT'
  | 'SUCCESS_FANFARE'
  | 'WARNING_MEME'
  | 'UI_FEEDBACK'
  | 'CRITICAL_ALARM';

export type SoundPackMode = 'TERMINAL_CHIMES' | '8BIT_MEGAMAN' | 'VIRAL_MEME' | 'HYBRID';

export interface AudioPreferences {
  enabled: boolean;
  volume: number; // 0.0 to 1.0
  pack: SoundPackMode;
  muteBackgroundAlerts: boolean;
}

export interface ActiveSoundPlaybackEvent {
  type: SoundEventType;
  label: string;
  durationMs: number;
  timestamp: number;
}

export interface SoundCategoryMeta {
  type: SoundEventType;
  shortLabel: string;
  title: string;
  description: string;
  durationLabel: string;
  colorHex: string;
}

export const SOUND_CATEGORIES_META: SoundCategoryMeta[] = [
  {
    type: 'TAKE_PROFIT',
    shortLabel: 'TAKE-PROFIT',
    title: 'Harmonischer TP-Chime',
    description: 'Take-Profit erreicht, profitabler Trade oder positiver Backtest-Abschluss',
    durationLabel: '0.38s',
    colorHex: '#089981',
  },
  {
    type: 'STOP_LOSS',
    shortLabel: 'STOP-LOSS',
    title: 'Gedämpfter SL-Chime',
    description: 'Stop-Loss ausgelöst, Positionsverlust oder Risikobegrenzung aktiv',
    durationLabel: '0.34s',
    colorHex: '#F59E0B',
  },
  {
    type: 'ORDER_FILL',
    shortLabel: 'ORDER-FILL',
    title: 'Terminal Execution Chime',
    description: 'Ausgeführte Trades, Paper-Buy/Sell Fills & DCA-Tranchen der Bots',
    durationLabel: '0.18s',
    colorHex: '#00E5FF',
  },
  {
    type: 'SCREENER_ALERT',
    shortLabel: 'RVOL / VOLA',
    title: 'Resonanz-Radar Chime',
    description: 'Neue RVOL-Spike (>2.0x) oder Volatilitäts-Anomalie im Screener',
    durationLabel: '0.42s',
    colorHex: '#60A5FA',
  },
  {
    type: 'UI_FEEDBACK',
    shortLabel: 'MICRO-CLICK',
    title: 'Dezenter Terminal-Click',
    description: 'Strategie gespeichert, Blueprint geladen, Modus- & Filter-Wechsel',
    durationLabel: '0.06s',
    colorHex: '#8B95A5',
  },
  {
    type: 'CRITICAL_ALARM',
    shortLabel: 'EMERGENCY',
    title: 'Sub-Gong / Kill Switch',
    description: 'Emergency Flatten All, Hard-Cap Blockade oder kritische Trennung',
    durationLabel: '0.50s',
    colorHex: '#F23645',
  },
];

const STORAGE_KEY = 'omega_terminal_audio_prefs_v2';

const DEFAULT_PREFS: AudioPreferences = {
  enabled: true,
  volume: 0.55,
  pack: 'TERMINAL_CHIMES',
  muteBackgroundAlerts: false,
};

type PlaybackListener = (event: ActiveSoundPlaybackEvent) => void;

class TerminalSoundEngine {
  private ctx: AudioContext | null = null;
  private prefs: AudioPreferences = { ...DEFAULT_PREFS };
  private lastPlayedMap: Map<SoundEventType, number> = new Map();
  private listeners: Set<PlaybackListener> = new Set();
  private noiseBuffer: AudioBuffer | null = null;

  constructor() {
    this.loadPrefs();
    if (typeof window !== 'undefined') {
      const unlock = () => {
        this.ensureContext();
        window.removeEventListener('pointerdown', unlock);
        window.removeEventListener('keydown', unlock);
      };
      window.addEventListener('pointerdown', unlock, { passive: true });
      window.addEventListener('keydown', unlock, { passive: true });
    }
  }

  private loadPrefs(): void {
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        this.prefs = {
          enabled: typeof parsed.enabled === 'boolean' ? parsed.enabled : DEFAULT_PREFS.enabled,
          volume:
            typeof parsed.volume === 'number'
              ? Math.max(0, Math.min(1, parsed.volume))
              : DEFAULT_PREFS.volume,
          pack:
            parsed.pack === 'TERMINAL_CHIMES' ||
            parsed.pack === '8BIT_MEGAMAN' ||
            parsed.pack === 'VIRAL_MEME' ||
            parsed.pack === 'HYBRID'
              ? parsed.pack
              : DEFAULT_PREFS.pack,
          muteBackgroundAlerts: Boolean(parsed.muteBackgroundAlerts),
        };
      }
    } catch {
      this.prefs = { ...DEFAULT_PREFS };
    }
  }

  private savePrefs(): void {
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(this.prefs));
    } catch {
      // ignore storage quota errors
    }
  }

  public getPreferences(): AudioPreferences {
    return { ...this.prefs };
  }

  public updatePreferences(patch: Partial<AudioPreferences>): AudioPreferences {
    this.prefs = {
      ...this.prefs,
      ...patch,
      volume:
        typeof patch.volume === 'number'
          ? Math.max(0, Math.min(1, patch.volume))
          : this.prefs.volume,
    };
    this.savePrefs();
    return this.getPreferences();
  }

  public toggleMute(): boolean {
    const next = !this.prefs.enabled;
    this.updatePreferences({ enabled: next });
    if (next) {
      this.play('UI_FEEDBACK', { force: true });
    }
    return next;
  }

  public subscribe(listener: PlaybackListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private emitPlayback(type: SoundEventType, label: string, durationMs: number): void {
    const evt: ActiveSoundPlaybackEvent = {
      type,
      label,
      durationMs: Math.min(600, durationMs),
      timestamp: Date.now(),
    };
    for (const listener of this.listeners) {
      try {
        listener(evt);
      } catch {
        // ignore listener error
      }
    }
  }

  private ensureContext(): AudioContext | null {
    if (typeof window === 'undefined') return null;
    if (!this.ctx) {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return null;
      this.ctx = new AudioCtx();
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume().catch(() => {});
    }
    return this.ctx;
  }

  /**
   * Generates a cached 1-second 8-bit LFSR-style noise buffer for retro sound effects
   */
  private getNoiseBuffer(ctx: AudioContext): AudioBuffer {
    if (this.noiseBuffer && this.noiseBuffer.sampleRate === ctx.sampleRate) {
      return this.noiseBuffer;
    }
    const bufferSize = ctx.sampleRate * 0.8;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const output = buffer.getChannelData(0);
    let lastVal = 0;
    for (let i = 0; i < bufferSize; i++) {
      if (i % 6 === 0) {
        lastVal = Math.random() * 2 - 1;
      }
      output[i] = lastVal;
    }
    this.noiseBuffer = buffer;
    return buffer;
  }

  /**
   * Helper: Pure, crystalline synthesizer chime with gentle attack and warm exponential decay.
   * Auto-disconnects on ended for zero memory leaks.
   */
  private scheduleChime(
    ctx: AudioContext,
    freq: number,
    startTime: number,
    durationSec: number,
    gainPeak: number,
    waveform: OscillatorType = 'sine',
    lowpassCutoff?: number
  ): void {
    const clampedDur = Math.max(0.04, Math.min(0.58, durationSec));
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = waveform;
    osc.frequency.setValueAtTime(Math.max(20, freq), startTime);

    const masterGain = Math.max(0.0001, gainPeak * this.prefs.volume);
    gain.gain.setValueAtTime(0.0001, startTime);
    // Soft attack (8ms) avoids pop/clicking artifacts
    gain.gain.linearRampToValueAtTime(masterGain, startTime + 0.008);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + clampedDur);

    if (lowpassCutoff) {
      const filter = ctx.createBiquadFilter();
      filter.type = 'lowpass';
      filter.frequency.setValueAtTime(lowpassCutoff, startTime);
      osc.connect(filter);
      filter.connect(gain);
    } else {
      osc.connect(gain);
    }

    gain.connect(ctx.destination);

    osc.onended = () => {
      try {
        osc.disconnect();
        gain.disconnect();
      } catch {
        // already disconnected
      }
    };

    osc.start(startTime);
    osc.stop(startTime + clampedDur + 0.01);
  }

  /**
   * Helper: Schedule a pitch-ramped oscillator note (useful for retro sounds or slides)
   */
  private scheduleNote(
    ctx: AudioContext,
    type: OscillatorType,
    freqStart: number,
    freqEnd: number | null,
    startTime: number,
    durationSec: number,
    gainPeak: number
  ): void {
    const clampedDur = Math.max(0.02, Math.min(0.58, durationSec));
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(Math.max(20, freqStart), startTime);
    if (freqEnd !== null && freqEnd !== freqStart) {
      osc.frequency.exponentialRampToValueAtTime(Math.max(20, freqEnd), startTime + clampedDur);
    }

    const masterGain = Math.max(0.0001, gainPeak * this.prefs.volume);
    gain.gain.setValueAtTime(0.0001, startTime);
    gain.gain.linearRampToValueAtTime(masterGain, startTime + Math.min(0.012, clampedDur * 0.2));
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + clampedDur);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.onended = () => {
      try {
        osc.disconnect();
        gain.disconnect();
      } catch {
        // already disconnected
      }
    };

    osc.start(startTime);
    osc.stop(startTime + clampedDur + 0.01);
  }

  /**
   * Helper: Schedule retro noise burst
   */
  private scheduleNoiseBurst(
    ctx: AudioContext,
    startTime: number,
    durationSec: number,
    bandpassFreq: number,
    gainPeak: number
  ): void {
    const clampedDur = Math.max(0.03, Math.min(0.5, durationSec));
    const source = ctx.createBufferSource();
    source.buffer = this.getNoiseBuffer(ctx);

    const filter = ctx.createBiquadFilter();
    filter.type = 'bandpass';
    filter.frequency.setValueAtTime(bandpassFreq, startTime);
    filter.Q.setValueAtTime(1.8, startTime);

    const gain = ctx.createGain();
    const masterGain = Math.max(0.0001, gainPeak * this.prefs.volume);
    gain.gain.setValueAtTime(masterGain, startTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + clampedDur);

    source.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);

    source.onended = () => {
      try {
        source.disconnect();
        filter.disconnect();
        gain.disconnect();
      } catch {
        // ignore
      }
    };

    source.start(startTime);
    source.stop(startTime + clampedDur);
  }

  /**
   * Main Trigger Method
   * @param eventType SoundEventType
   * @param options { force?: boolean; isBackground?: boolean }
   */
  public play(
    eventType: SoundEventType,
    options?: { force?: boolean; isBackground?: boolean }
  ): void {
    if (!options?.force) {
      if (!this.prefs.enabled || this.prefs.volume <= 0.001) return;
      if (options?.isBackground && this.prefs.muteBackgroundAlerts) return;
    }

    // Map aliases
    let resolvedType: SoundEventType = eventType;
    if (eventType === 'SUCCESS_FANFARE') resolvedType = 'TAKE_PROFIT';
    if (eventType === 'WARNING_MEME') resolvedType = 'STOP_LOSS';

    const nowMs = Date.now();
    const lastMs = this.lastPlayedMap.get(resolvedType) || 0;
    const minCooldownMs = options?.force
      ? 30
      : options?.isBackground
      ? 3500
      : resolvedType === 'UI_FEEDBACK'
      ? 60
      : 180;

    if (nowMs - lastMs < minCooldownMs) return;
    this.lastPlayedMap.set(resolvedType, nowMs);

    const ctx = this.ensureContext();
    if (!ctx) return;

    const t0 = ctx.currentTime + 0.005;
    const pack = this.prefs.pack;

    // =========================================================================
    // 1. DEFAULT: DEZENTE TERMINAL-SYNTH-CHIMES (Subtil, elegant, nie aufdringlich)
    // =========================================================================
    if (pack === 'TERMINAL_CHIMES') {
      switch (resolvedType) {
        case 'TAKE_PROFIT': {
          // Harmonisch aufsteigender Major-Pentatonic Chime: E6 (1318.5) -> G#6 (1661.2) -> B6 (1975.5) + E7 (2637) Shimmer
          this.scheduleChime(ctx, 1318.51, t0, 0.32, 0.28, 'sine');
          this.scheduleChime(ctx, 1661.22, t0 + 0.07, 0.34, 0.26, 'sine');
          this.scheduleChime(ctx, 1975.53, t0 + 0.14, 0.38, 0.28, 'triangle');
          this.scheduleChime(ctx, 2637.02, t0 + 0.20, 0.24, 0.14, 'sine');
          this.emitPlayback('TAKE_PROFIT', 'TP HARMONIC CHIME', 380);
          break;
        }

        case 'STOP_LOSS': {
          // Sanfter, gedämpfter Abwärts-Intervall-Chime: D#5 (622.25) -> G#4 (415.3) mit warmem Lowpass-Filter
          this.scheduleChime(ctx, 622.25, t0, 0.24, 0.25, 'sine', 1400);
          this.scheduleChime(ctx, 415.3, t0 + 0.08, 0.32, 0.26, 'triangle', 1100);
          this.emitPlayback('STOP_LOSS', 'SL SOFT CHIME', 340);
          break;
        }

        case 'ORDER_FILL': {
          // Kristallklarer, knackiger Terminal Execution Chime (F#6 1479.98 + C#7 2217.46)
          this.scheduleChime(ctx, 1479.98, t0, 0.16, 0.28, 'sine');
          this.scheduleChime(ctx, 2217.46, t0 + 0.035, 0.18, 0.22, 'triangle');
          this.emitPlayback('ORDER_FILL', 'EXECUTION CHIME', 180);
          break;
        }

        case 'SCREENER_ALERT': {
          // Subtiler Resonanz-Radar Chime für RVOL-Spikes & Volatilitäts-Anomalien (A5 880Hz -> E6 1320Hz mit Glasglocken-Oberton)
          this.scheduleChime(ctx, 880.0, t0, 0.38, 0.24, 'sine');
          this.scheduleChime(ctx, 1318.51, t0 + 0.06, 0.36, 0.26, 'sine');
          this.scheduleChime(ctx, 2637.02, t0 + 0.10, 0.22, 0.10, 'triangle');
          this.emitPlayback('SCREENER_ALERT', 'RVOL / VOLA CHIME', 420);
          break;
        }

        case 'UI_FEEDBACK': {
          // Subtiler Micro-Click / Soft-Pip
          this.scheduleChime(ctx, 1046.5, t0, 0.06, 0.18, 'sine', 2000);
          this.emitPlayback('UI_FEEDBACK', 'TERMINAL CLICK', 60);
          break;
        }

        case 'CRITICAL_ALARM': {
          // Dezent tiefer Sub-Double-Gong für Emergency Kill / Flatten
          this.scheduleChime(ctx, 220.0, t0, 0.45, 0.32, 'triangle', 600);
          this.scheduleChime(ctx, 110.0, t0 + 0.08, 0.48, 0.35, 'sine');
          this.emitPlayback('CRITICAL_ALARM', 'TERMINAL FLATTEN', 500);
          break;
        }
      }
      return;
    }

    // =========================================================================
    // 2. 8-BIT NES 2A03 PROFILE (Mega Man Style)
    // =========================================================================
    if (pack === '8BIT_MEGAMAN') {
      switch (resolvedType) {
        case 'TAKE_PROFIT': {
          const notes = [523.25, 659.25, 783.99, 1046.5];
          notes.forEach((f, idx) => {
            this.scheduleNote(ctx, 'square', f, null, t0 + idx * 0.08, 0.08, 0.26);
            this.scheduleNote(ctx, 'triangle', f * 0.5, null, t0 + idx * 0.08, 0.08, 0.22);
          });
          this.emitPlayback('TAKE_PROFIT', '8-BIT TP FANFARE', 360);
          break;
        }
        case 'STOP_LOSS': {
          const dmg = [659.25, 523.25, 415.3, 329.63];
          dmg.forEach((f, idx) => {
            this.scheduleNote(ctx, 'square', f, f * 0.9, t0 + idx * 0.08, 0.08, 0.24);
          });
          this.scheduleNoiseBurst(ctx, t0, 0.15, 800, 0.18);
          this.emitPlayback('STOP_LOSS', '8-BIT SL HIT', 340);
          break;
        }
        case 'ORDER_FILL': {
          this.scheduleNote(ctx, 'square', 1400, 400, t0, 0.09, 0.25);
          this.scheduleNote(ctx, 'square', 987.77, null, t0 + 0.08, 0.12, 0.28);
          this.emitPlayback('ORDER_FILL', '8-BIT BUSTER FILL', 200);
          break;
        }
        case 'SCREENER_ALERT': {
          this.scheduleNote(ctx, 'square', 740.0, 1108.73, t0, 0.14, 0.24);
          this.scheduleNote(ctx, 'square', 1479.98, null, t0 + 0.16, 0.15, 0.26);
          this.emitPlayback('SCREENER_ALERT', '8-BIT RADAR SONAR', 320);
          break;
        }
        case 'UI_FEEDBACK': {
          this.scheduleNote(ctx, 'square', 987.77, null, t0, 0.05, 0.2);
          this.emitPlayback('UI_FEEDBACK', '8-BIT PIP', 60);
          break;
        }
        case 'CRITICAL_ALARM': {
          this.scheduleNote(ctx, 'square', 440, 110, t0, 0.35, 0.32);
          this.scheduleNoiseBurst(ctx, t0, 0.2, 450, 0.25);
          this.emitPlayback('CRITICAL_ALARM', '8-BIT KO EXPLODE', 400);
          break;
        }
      }
      return;
    }

    // =========================================================================
    // 3. VIRAL MEME PROFILE
    // =========================================================================
    if (pack === 'VIRAL_MEME') {
      switch (resolvedType) {
        case 'TAKE_PROFIT': {
          // MLG Victory Triad
          [523.25, 659.25, 783.99, 1046.5].forEach((f) => {
            this.scheduleNote(ctx, 'sawtooth', f, null, t0, 0.16, 0.16);
            this.scheduleNote(ctx, 'sawtooth', f * 1.12, null, t0 + 0.18, 0.24, 0.18);
          });
          this.emitPlayback('TAKE_PROFIT', 'MEME VICTORY HORN', 420);
          break;
        }
        case 'STOP_LOSS': {
          // Bruh slide
          this.scheduleNote(ctx, 'sawtooth', 369.99, 329.63, t0, 0.15, 0.26);
          this.scheduleNote(ctx, 'sawtooth', 329.63, 233.08, t0 + 0.15, 0.22, 0.28);
          this.emitPlayback('STOP_LOSS', 'MEME BRUH FAIL', 380);
          break;
        }
        case 'ORDER_FILL': {
          this.scheduleNote(ctx, 'square', 987.77, null, t0, 0.07, 0.28);
          this.scheduleNote(ctx, 'square', 1318.51, null, t0 + 0.07, 0.22, 0.32);
          this.emitPlayback('ORDER_FILL', 'KA-CHING FILL', 300);
          break;
        }
        case 'SCREENER_ALERT': {
          this.scheduleNote(ctx, 'sawtooth', 622.25, 587.33, t0, 0.18, 0.26);
          this.scheduleNote(ctx, 'triangle', 1244.5, 932.33, t0, 0.38, 0.22);
          this.emitPlayback('SCREENER_ALERT', 'SUS RADAR PING', 380);
          break;
        }
        case 'UI_FEEDBACK': {
          this.scheduleNote(ctx, 'sine', 520, 1180, t0, 0.07, 0.25);
          this.emitPlayback('UI_FEEDBACK', 'MEME POP', 80);
          break;
        }
        case 'CRITICAL_ALARM': {
          this.scheduleNote(ctx, 'sine', 145, 32, t0, 0.48, 0.45);
          this.scheduleNoiseBurst(ctx, t0, 0.14, 380, 0.3);
          this.emitPlayback('CRITICAL_ALARM', 'VINE BOOM SUB', 480);
          break;
        }
      }
      return;
    }

    // =========================================================================
    // 4. HYBRID MIX PROFILE
    // =========================================================================
    if (resolvedType === 'TAKE_PROFIT') {
      this.scheduleChime(ctx, 1318.51, t0, 0.32, 0.28, 'sine');
      this.scheduleChime(ctx, 1661.22, t0 + 0.07, 0.34, 0.26, 'sine');
      this.scheduleChime(ctx, 1975.53, t0 + 0.14, 0.38, 0.28, 'triangle');
      this.emitPlayback('TAKE_PROFIT', 'TP HARMONIC CHIME', 380);
    } else if (resolvedType === 'STOP_LOSS') {
      this.scheduleChime(ctx, 622.25, t0, 0.24, 0.25, 'sine', 1400);
      this.scheduleChime(ctx, 415.3, t0 + 0.08, 0.32, 0.26, 'triangle', 1100);
      this.emitPlayback('STOP_LOSS', 'SL SOFT CHIME', 340);
    } else if (resolvedType === 'ORDER_FILL') {
      this.scheduleChime(ctx, 1479.98, t0, 0.16, 0.28, 'sine');
      this.scheduleChime(ctx, 2217.46, t0 + 0.035, 0.18, 0.22, 'triangle');
      this.emitPlayback('ORDER_FILL', 'EXECUTION CHIME', 180);
    } else if (resolvedType === 'SCREENER_ALERT') {
      this.scheduleChime(ctx, 880.0, t0, 0.38, 0.24, 'sine');
      this.scheduleChime(ctx, 1318.51, t0 + 0.06, 0.36, 0.26, 'sine');
      this.emitPlayback('SCREENER_ALERT', 'RVOL / VOLA CHIME', 420);
    } else if (resolvedType === 'CRITICAL_ALARM') {
      this.scheduleNote(ctx, 'sine', 145, 32, t0, 0.48, 0.45);
      this.emitPlayback('CRITICAL_ALARM', 'SUB GONG IMPACT', 480);
    } else {
      this.scheduleChime(ctx, 1046.5, t0, 0.06, 0.18, 'sine', 2000);
      this.emitPlayback('UI_FEEDBACK', 'TERMINAL CLICK', 60);
    }
  }
}

export const arcadeSoundEngine = new TerminalSoundEngine();
export const terminalSoundEngine = arcadeSoundEngine;
