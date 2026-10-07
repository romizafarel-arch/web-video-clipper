export interface TimedWord {
  word: string;
  start: number;
  end: number;
}

export interface TranscriptCue {
  text: string;
  start: number;
  end: number;
  words: TimedWord[];
}

export const ILLUSTRATION_TRANSCRIPT_TEXT =
  'Selamat datang di podcast naik kelas, podcast-nya mereka yang terus berkarya namun tetap otentik.';

export const ILLUSTRATION_TIMED_WORDS: TimedWord[] = [
  { word: 'Selamat', start: 0.0, end: 0.72 },
  { word: 'datang', start: 0.72, end: 1.08 },
  { word: 'di', start: 1.08, end: 1.32 },
  { word: 'podcast', start: 1.32, end: 1.74 },
  { word: 'naik', start: 1.74, end: 2.05 },
  { word: 'kelas,', start: 2.05, end: 2.45 },
  { word: 'podcast-nya', start: 2.5, end: 3.14 },
  { word: 'mereka', start: 3.14, end: 3.36 },
  { word: 'yang', start: 3.36, end: 3.6 },
  { word: 'terus', start: 3.6, end: 3.82 },
  { word: 'berkarya', start: 3.82, end: 4.4 },
  { word: 'namun', start: 4.4, end: 4.88 },
  { word: 'tetap', start: 4.88, end: 5.3 },
  { word: 'otentik.', start: 5.3, end: 5.95 },
];

export const ILLUSTRATION_CUES: TranscriptCue[] = [
  {
    text: 'Selamat datang di podcast naik kelas,',
    start: 0.0,
    end: 2.48,
    words: [
      { word: 'Selamat', start: 0.0, end: 0.72 },
      { word: 'datang', start: 0.72, end: 1.08 },
      { word: 'di', start: 1.08, end: 1.32 },
      { word: 'podcast', start: 1.32, end: 1.74 },
      { word: 'naik', start: 1.74, end: 2.05 },
      { word: 'kelas,', start: 2.05, end: 2.45 },
    ],
  },
  {
    text: 'podcast-nya mereka yang terus berkarya namun tetap otentik.',
    start: 2.48,
    end: 6.0,
    words: [
      { word: 'podcast-nya', start: 2.5, end: 3.14 },
      { word: 'mereka', start: 3.14, end: 3.36 },
      { word: 'yang', start: 3.36, end: 3.6 },
      { word: 'terus', start: 3.6, end: 3.82 },
      { word: 'berkarya', start: 3.82, end: 4.4 },
      { word: 'namun', start: 4.4, end: 4.88 },
      { word: 'tetap', start: 4.88, end: 5.3 },
      { word: 'otentik.', start: 5.3, end: 5.95 },
    ],
  },
];
