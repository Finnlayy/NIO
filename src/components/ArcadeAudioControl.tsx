import React, { useState, useEffect, useRef } from 'react';
import { Volume2, VolumeX, Play, Sliders, Radio } from 'lucide-react';
import {
  arcadeSoundEngine,
  AudioPreferences,
  SoundPackMode,
  SOUND_CATEGORIES_META,
  ActiveSoundPlaybackEvent,
} from '../services/arcadeSoundEngine';

export const ArcadeAudioControl: React.FC = () => {
  const [prefs, setPrefs] = useState<AudioPreferences>(() =>
    arcadeSoundEngine.getPreferences()
  );
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [activeSound, setActiveSound] = useState<ActiveSoundPlaybackEvent | null>(null);
  const clearTimerRef = useRef<number | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const unsubscribe = arcadeSoundEngine.subscribe((evt) => {
      setActiveSound(evt);
      if (clearTimerRef.current) {
        window.clearTimeout(clearTimerRef.current);
      }
      clearTimerRef.current = window.setTimeout(() => {
        setActiveSound(null);
      }, evt.durationMs + 60);
    });

    return () => {
      unsubscribe();
      if (clearTimerRef.current) {
        window.clearTimeout(clearTimerRef.current);
      }
    };
  }, []);

  // Close popover on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handleOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    window.addEventListener('mousedown', handleOutside);
    return () => window.removeEventListener('mousedown', handleOutside);
  }, [isOpen]);

  const handleToggleMute = (e: React.MouseEvent) => {
    e.stopPropagation();
    const nextEnabled = arcadeSoundEngine.toggleMute();
    setPrefs(arcadeSoundEngine.getPreferences());
  };

  const handleVolumeChange = (val: number) => {
    const updated = arcadeSoundEngine.updatePreferences({
      volume: val,
      enabled: val > 0 ? true : prefs.enabled,
    });
    setPrefs(updated);
  };

  const handlePackChange = (pack: SoundPackMode) => {
    const updated = arcadeSoundEngine.updatePreferences({ pack, enabled: true });
    setPrefs(updated);
    arcadeSoundEngine.play('UI_FEEDBACK', { force: true });
  };

  const handleToggleBgMute = () => {
    const updated = arcadeSoundEngine.updatePreferences({
      muteBackgroundAlerts: !prefs.muteBackgroundAlerts,
    });
    setPrefs(updated);
    arcadeSoundEngine.play('UI_FEEDBACK', { force: true });
  };

  const packShortLabel =
    prefs.pack === 'TERMINAL_CHIMES'
      ? 'CHIMES'
      : prefs.pack === '8BIT_MEGAMAN'
      ? '8-BIT'
      : prefs.pack === 'VIRAL_MEME'
      ? 'MEME'
      : 'HYBRID';

  return (
    <div ref={containerRef} className="relative flex items-center shrink-0">
      {/* 1-Click Header Mute Toggle + Terminal Chimes Control */}
      <div
        className={`flex items-center border text-[10px] font-mono tabular-nums transition-colors ${
          activeSound
            ? 'bg-[#00E5FF]/20 border-[#00E5FF] text-[#00E5FF]'
            : prefs.enabled
            ? 'bg-[#07090E] border-[#1B2230] text-[#E6EDF3] hover:border-[#00E5FF]/50'
            : 'bg-[#07090E] border-[#F23645]/40 text-[#8B95A5]'
        }`}
      >
        {/* Dedicated 1-Click Mute Toggle Button */}
        <button
          type="button"
          onClick={handleToggleMute}
          title={
            prefs.enabled
              ? 'Audio stummschalten (1-Klick Mute)'
              : 'Terminal-Synth-Chimes wieder aktivieren'
          }
          className={`px-2 py-1 flex items-center gap-1.5 transition-colors border-r border-[#1B2230] whitespace-nowrap shrink-0 ${
            prefs.enabled
              ? 'hover:bg-[#00E5FF]/10 text-[#00E5FF]'
              : 'hover:bg-[#F23645]/10 text-[#F23645]'
          }`}
        >
          {prefs.enabled ? (
            <>
              <Volume2 className="w-3.5 h-3.5 text-[#00E5FF]" />
              <span className="font-bold hidden sm:inline">TON AN</span>
            </>
          ) : (
            <>
              <VolumeX className="w-3.5 h-3.5 text-[#F23645]" />
              <span className="font-bold text-[#F23645]">STUMM</span>
            </>
          )}
        </button>

        {/* Audio Mode & Soundboard Popover Trigger */}
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          title="Terminal-Synth Sound-Einstellungen & Soundboard öffnen"
          className="px-2 py-1 flex items-center gap-1.5 whitespace-nowrap shrink-0 hover:text-[#00E5FF]"
        >
          {activeSound ? (
            <>
              <span className="inline-flex items-end gap-0.5 h-2.5">
                <span className="w-0.5 h-2.5 bg-[#00E5FF] animate-pulse" />
                <span className="w-0.5 h-1.5 bg-[#00E5FF] animate-pulse" />
                <span className="w-0.5 h-2 bg-[#00E5FF] animate-pulse" />
              </span>
              <span className="font-bold text-[#00E5FF] max-w-[110px] truncate">
                {activeSound.label}
              </span>
            </>
          ) : (
            <>
              <span className={prefs.enabled ? 'text-[#00E5FF] font-bold' : 'text-[#8B95A5]'}>
                {packShortLabel}
              </span>
              <span className="text-[#8B95A5]">{Math.round(prefs.volume * 100)}%</span>
            </>
          )}
        </button>
      </div>

      {/* Soundboard & Synthesizer Configuration Popover */}
      {isOpen && (
        <div className="absolute right-0 top-full mt-1.5 w-[350px] bg-[#0C1017] border border-[#263042] shadow-2xl z-50 p-3 font-mono text-xs select-none">
          {/* Header */}
          <div className="flex items-center justify-between pb-2 mb-2.5 border-b border-[#1B2230]">
            <div className="flex items-center gap-1.5">
              <Sliders className="w-3.5 h-3.5 text-[#00E5FF]" />
              <span className="font-bold text-[#E6EDF3] text-[11px] tracking-wide">
                TERMINAL-SYNTH AUDIO ENGINE
              </span>
            </div>
            <button
              type="button"
              onClick={handleToggleMute}
              className={`px-2 py-0.5 text-[10px] font-bold border whitespace-nowrap ${
                prefs.enabled
                  ? 'bg-[#089981]/20 border-[#089981] text-[#089981]'
                  : 'bg-[#F23645]/20 border-[#F23645] text-[#F23645]'
              }`}
            >
              {prefs.enabled ? 'AKTIV' : 'STUMMGESCHALTET'}
            </button>
          </div>

          {/* Master Volume Slider */}
          <div className="mb-3">
            <div className="flex items-center justify-between text-[10px] text-[#8B95A5] mb-1 tabular-nums">
              <span>MASTER-LAUTSTÄRKE (DEZENTE SYNTH-CHIMES)</span>
              <span className="text-[#00E5FF] font-bold">{Math.round(prefs.volume * 100)}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={prefs.volume}
              onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
              onMouseUp={() => arcadeSoundEngine.play('UI_FEEDBACK', { force: true })}
              className="w-full accent-[#00E5FF] cursor-pointer h-1.5 bg-[#07090E]"
            />
          </div>

          {/* Sound Profile Selector */}
          <div className="mb-3">
            <div className="text-[10px] text-[#8B95A5] mb-1">SOUND-STIL</div>
            <div className="grid grid-cols-2 gap-1">
              {(
                [
                  { id: 'TERMINAL_CHIMES', label: 'DEZENTE CHIMES (EMPFOHLEN)' },
                  { id: '8BIT_MEGAMAN', label: '8-BIT ARCADE NES' },
                  { id: 'VIRAL_MEME', label: 'VIRAL MEME' },
                  { id: 'HYBRID', label: 'HYBRID MIX' },
                ] as const
              ).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handlePackChange(item.id)}
                  className={`py-1 px-1.5 text-[9px] font-bold border text-center whitespace-nowrap transition-colors ${
                    prefs.pack === item.id
                      ? 'bg-[#00E5FF]/20 border-[#00E5FF] text-[#00E5FF]'
                      : 'bg-[#07090E] border-[#1B2230] text-[#8B95A5] hover:text-[#E6EDF3]'
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Background Screener Radar Toggle */}
          <div className="flex items-center justify-between py-1.5 px-2 mb-3 bg-[#07090E] border border-[#1B2230]">
            <div className="flex items-center gap-1.5">
              <Radio className="w-3 h-3 text-[#60A5FA]" />
              <div>
                <div className="text-[10px] text-[#E6EDF3] leading-none">Screener RVOL / Vola Radar</div>
                <div className="text-[8px] text-[#8B95A5] mt-0.5">Tonsignal bei Screener-Anomalien</div>
              </div>
            </div>
            <button
              type="button"
              onClick={handleToggleBgMute}
              className={`px-1.5 py-0.5 text-[9px] font-bold border ${
                !prefs.muteBackgroundAlerts
                  ? 'border-[#00E5FF]/50 text-[#00E5FF] bg-[#00E5FF]/10'
                  : 'border-[#1B2230] text-[#8B95A5]'
              }`}
            >
              {!prefs.muteBackgroundAlerts ? 'AKTIV' : 'STUMM'}
            </button>
          </div>

          {/* Interactive Sound Preview Grid */}
          <div className="text-[10px] text-[#8B95A5] mb-1.5 flex items-center justify-between">
            <span>SOUNDS VORHÖREN (KLICKEN ZUM TESTEN)</span>
            <span className="text-[9px] text-[#00E5FF]">≤ 0.5s CAP</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {SOUND_CATEGORIES_META.map((cat) => {
              const isPlayingThis = activeSound?.type === cat.type;
              return (
                <button
                  key={cat.type}
                  type="button"
                  onClick={() => arcadeSoundEngine.play(cat.type, { force: true })}
                  title={cat.description}
                  className={`p-1.5 border text-left transition-colors flex flex-col justify-between ${
                    isPlayingThis
                      ? 'bg-[#00E5FF]/20 border-[#00E5FF]'
                      : 'bg-[#07090E] border-[#1B2230] hover:border-[#263042] hover:bg-[#131924]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-1 w-full">
                    <span
                      className="text-[10px] font-bold truncate"
                      style={{ color: cat.colorHex }}
                    >
                      {cat.shortLabel}
                    </span>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-[8px] text-[#8B95A5] tabular-nums">
                        {cat.durationLabel}
                      </span>
                      <Play className="w-2.5 h-2.5 text-[#E6EDF3]" />
                    </div>
                  </div>
                  <div className="text-[9px] text-[#8B95A5] truncate mt-0.5">{cat.title}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
