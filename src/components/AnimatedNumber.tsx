import React, { useEffect, useRef, useState, memo } from 'react';

export interface AnimatedNumberProps {
  value: number;
  precision?: number;
  prefix?: string;
  suffix?: string;
  formatter?: (val: number) => string;
  className?: string;
  flashOnUpdate?: boolean;
  showSign?: boolean;
  durationMs?: number;
}

/**
 * High-performance, stutter and tearing-free floating-point number animator.
 * Uses requestAnimationFrame with exponential damping and hardware-accelerated transforms.
 * Enforces tabular-nums font glyphs to eliminate horizontal jitter and layout reflow.
 */
export const AnimatedNumber: React.FC<AnimatedNumberProps> = memo(({
  value,
  precision = 2,
  prefix = '',
  suffix = '',
  formatter,
  className = '',
  flashOnUpdate = true,
  showSign = false,
  durationMs = 500,
}) => {
  const [displayValue, setDisplayValue] = useState<number>(() => (Number.isFinite(value) ? value : 0));
  const [flashColor, setFlashColor] = useState<'green' | 'red' | null>(null);
  
  const currentValRef = useRef<number>(displayValue);
  const targetValRef = useRef<number>(value);
  const startTimeRef = useRef<number>(0);
  const startValRef = useRef<number>(displayValue);
  const animFrameIdRef = useRef<number | null>(null);
  const flashTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const nextTarget = Number.isFinite(value) ? value : 0;
    const prevTarget = targetValRef.current;

    if (Math.abs(nextTarget - prevTarget) > 1e-9) {
      if (flashOnUpdate) {
        if (nextTarget > prevTarget) {
          setFlashColor('green');
        } else if (nextTarget < prevTarget) {
          setFlashColor('red');
        }
        if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
        flashTimeoutRef.current = setTimeout(() => {
          setFlashColor(null);
        }, 650);
      }

      startValRef.current = currentValRef.current;
      targetValRef.current = nextTarget;
      startTimeRef.current = performance.now();

      const animate = (now: number) => {
        const elapsed = now - startTimeRef.current;
        const progress = Math.min(1, elapsed / durationMs);
        
        // Quintic ease-out: 1 - pow(1 - x, 5) for ultra-smooth fluid stopping without sudden snap
        const ease = 1 - Math.pow(1 - progress, 5);
        const current = startValRef.current + (targetValRef.current - startValRef.current) * ease;

        currentValRef.current = current;
        setDisplayValue(current);

        if (progress < 1) {
          animFrameIdRef.current = requestAnimationFrame(animate);
        } else {
          currentValRef.current = targetValRef.current;
          setDisplayValue(targetValRef.current);
        }
      };

      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
      }
      animFrameIdRef.current = requestAnimationFrame(animate);
    }

    return () => {
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
    };
  }, [value, durationMs, flashOnUpdate]);

  // Format the numerical output
  let formattedNumber = '';
  if (formatter) {
    formattedNumber = formatter(displayValue);
  } else {
    const isNegative = displayValue < -1e-9;
    const absVal = Math.abs(displayValue);
    const formattedAbs = absVal.toLocaleString(undefined, {
      minimumFractionDigits: precision,
      maximumFractionDigits: precision,
    });
    const signPrefix = isNegative ? '-' : showSign && absVal > 1e-9 ? '+' : '';
    formattedNumber = `${signPrefix}${prefix}${formattedAbs}${suffix}`;
  }

  return (
    <span
      className={`inline-block tabular-nums transition-colors duration-500 font-mono ${
        flashColor === 'green'
          ? 'text-emerald-300 drop-shadow-[0_0_8px_rgba(16,185,129,0.5)]'
          : flashColor === 'red'
          ? 'text-rose-300 drop-shadow-[0_0_8px_rgba(244,63,94,0.5)]'
          : ''
      } ${className}`}
      style={{
        fontVariantNumeric: 'tabular-nums',
        willChange: 'transform, opacity, color',
        transform: 'translateZ(0)',
        backfaceVisibility: 'hidden',
      }}
    >
      {formattedNumber}
    </span>
  );
});

AnimatedNumber.displayName = 'AnimatedNumber';

/**
 * Currency convenience component ($123,456.78)
 */
export const AnimatedCurrency: React.FC<{
  value: number;
  precision?: number;
  className?: string;
  showSign?: boolean;
}> = memo(({ value, precision = 2, className = '', showSign = false }) => {
  return (
    <AnimatedNumber
      value={value}
      precision={precision}
      prefix="$"
      showSign={showSign}
      className={className}
    />
  );
});
AnimatedCurrency.displayName = 'AnimatedCurrency';

/**
 * Percentage convenience component (+1.25%)
 */
export const AnimatedPercent: React.FC<{
  value: number;
  precision?: number;
  className?: string;
  showSign?: boolean;
}> = memo(({ value, precision = 2, className = '', showSign = true }) => {
  return (
    <AnimatedNumber
      value={value}
      precision={precision}
      suffix="%"
      showSign={showSign}
      className={className}
    />
  );
});
AnimatedPercent.displayName = 'AnimatedPercent';
