let audioContext: AudioContext | null = null;

function getContext() {
  audioContext ??= new AudioContext();
  return audioContext;
}

function tone(
  context: AudioContext,
  frequency: number,
  duration: number,
  volume: number,
  type: OscillatorType,
) {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  const now = context.currentTime;
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, now);
  oscillator.frequency.exponentialRampToValueAtTime(frequency * 0.62, now + duration);
  gain.gain.setValueAtTime(volume, now);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start(now);
  oscillator.stop(now + duration);
}

export function playMoveSound(capture: boolean) {
  const context = getContext();
  if (context.state === "suspended") void context.resume();
  tone(context, capture ? 126 : 210, capture ? 0.32 : 0.18, 0.09, "triangle");
  tone(context, capture ? 520 : 390, capture ? 0.16 : 0.1, 0.035, "square");
}
