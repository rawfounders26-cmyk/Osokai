import { useId } from 'react';
import Svg, { Path, Defs, LinearGradient, Stop } from 'react-native-svg';

// Vivid folder palette, cycled through the stack (newest first).
export const FOLDER_ACCENTS = ['#f5c518', '#46c46a', '#e5484d', '#6366f1', '#38bdf8'];
export const FOLDER_DARK_INK = '#14100a';

const MON_SHORT = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];

/** Short corner label, e.g. "sep - 26". */
export function shortLabel(yearMonth) {
  const m = parseInt(yearMonth.slice(5, 7), 10);
  const yy = yearMonth.slice(2, 4);
  return `${MON_SHORT[((m - 1) % 12 + 12) % 12] ?? ''} - ${yy}`;
}

export function accentForMonth(months, yearMonth) {
  const idx = months.findIndex(m => m.month === yearMonth);
  return FOLDER_ACCENTS[((idx % FOLDER_ACCENTS.length) + FOLDER_ACCENTS.length) % FOLDER_ACCENTS.length];
}

export function inkForAccent(accent) {
  return accent === '#f5c518' || accent === '#46c46a' ? FOLDER_DARK_INK : '#ffffff';
}

function folderBackPath() {
  return [
    'M 0,74', 'L 0,22', 'Q 0,4 18,4', 'L 122,4', 'Q 140,4 140,22', 'L 140,28',
    'Q 140,46 158,46', 'L 282,46', 'Q 300,46 300,64', 'L 300,164',
    'Q 300,182 282,182', 'L 18,182', 'Q 0,182 0,164', 'Z',
  ].join(' ');
}

/** ONE standalone desktop-style folder: back panel + wide tab + long front. */
export function MonthFolderShape({ color }) {
  const gid = useId().replace(/[^a-zA-Z0-9]/g, '');
  return (
    <Svg width="100%" height={228} viewBox="0 0 300 224">
      <Defs>
        <LinearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <Stop offset="0" stopColor="#ffffff" stopOpacity="0.28" />
          <Stop offset="0.35" stopColor="#ffffff" stopOpacity="0.06" />
          <Stop offset="1" stopColor="#000000" stopOpacity="0.22" />
        </LinearGradient>
      </Defs>
      <Path d={folderBackPath()} fill={color} />
      <Path
        d="M 8,80 L 8,202 Q 8,216 22,216 L 278,216 Q 292,216 292,202 L 292,94 Q 292,80 278,80 L 22,80 Q 8,80 8,94 Z"
        fill={color}
      />
      <Path
        d="M 8,80 L 8,202 Q 8,216 22,216 L 278,216 Q 292,216 292,202 L 292,94 Q 292,80 278,80 L 22,80 Q 8,80 8,94 Z"
        fill={`url(#${gid})`}
      />
      <Path d={folderBackPath()} fill={`url(#${gid})`} opacity={0.6} />
    </Svg>
  );
}
