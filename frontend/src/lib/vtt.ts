import type { SubtitleCue } from '../types';

export function parseVttTimestamp(timeStr: string): number {
  const clean = timeStr.trim().replace(',', '.');
  const parts = clean.split(':');
  if (parts.length === 3) {
    const hours = parseFloat(parts[0]) || 0;
    const minutes = parseFloat(parts[1]) || 0;
    const seconds = parseFloat(parts[2]) || 0;
    return Math.max(0, hours * 3600 + minutes * 60 + seconds);
  } else if (parts.length === 2) {
    const minutes = parseFloat(parts[0]) || 0;
    const seconds = parseFloat(parts[1]) || 0;
    return Math.max(0, minutes * 60 + seconds);
  }
  const val = parseFloat(clean);
  return Number.isFinite(val) ? Math.max(0, val) : 0;
}

export function formatVttTimestamp(seconds: number): string {
  const s = Math.max(0, seconds);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = Math.floor(s % 60);
  const ms = Math.floor((s % 1) * 1000);
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(3, '0')}`;
}

export function formatTimeDisplay(seconds: number): string {
  const s = Math.max(0, seconds);
  const mins = Math.floor(s / 60);
  const secs = Math.floor(s % 60);
  const ms = Math.floor((s % 1) * 10);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms}`;
}

export function parseVTT(vttText: string): SubtitleCue[] {
  if (!vttText || typeof vttText !== 'string') return [];
  const cues: SubtitleCue[] = [];
  const lines = vttText.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  let i = 0;

  // Skip header or metadata
  while (i < lines.length) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith('WEBVTT') || trimmed.startsWith('NOTE') || trimmed.startsWith('STYLE')) {
      i++;
      continue;
    }
    if (trimmed === '') {
      i++;
      continue;
    }
    break;
  }

  while (i < lines.length) {
    const line = lines[i].trim();
    if (!line) {
      i++;
      continue;
    }

    let timeLine = line;
    let cueId = `cue-${cues.length + 1}`;

    // If line is identifier (no arrow) and next line has arrow
    if (!line.includes('-->') && i + 1 < lines.length && lines[i + 1].includes('-->')) {
      cueId = line;
      i++;
      timeLine = lines[i].trim();
    }

    if (timeLine.includes('-->')) {
      const parts = timeLine.split('-->');
      const startStr = parts[0]?.trim() || '';
      const endPart = parts[1]?.trim() || '';
      const endStr = endPart.split(/\s+/)[0] || '';

      const start = parseVttTimestamp(startStr);
      const end = parseVttTimestamp(endStr);

      i++;
      const textLines: string[] = [];
      while (i < lines.length && lines[i].trim() !== '') {
        textLines.push(lines[i].trim());
        i++;
      }

      if (end > start) {
        cues.push({
          id: cueId || `cue-${cues.length + 1}`,
          start: Number(start.toFixed(3)),
          end: Number(end.toFixed(3)),
          text: textLines.join('\n'),
        });
      }
    } else {
      i++;
    }
  }

  return cues;
}

export function serializeVTT(cues: SubtitleCue[]): string {
  let output = 'WEBVTT\n\n';
  cues.forEach((cue, index) => {
    output += `${index + 1}\n`;
    output += `${formatVttTimestamp(cue.start)} --> ${formatVttTimestamp(cue.end)}\n`;
    output += `${cue.text.trim()}\n\n`;
  });
  return output;
}
