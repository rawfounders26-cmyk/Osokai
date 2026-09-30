import { Dimensions } from 'react-native';
import Svg, { Path, Circle, Line, Text as SvgText } from 'react-native-svg';
import { colors } from '../../services/theme';

/** Monthly activity line graph: daily task counts of one month. */
export function UsageGraph({ values, accent }) {
  const width = Dimensions.get('window').width - 12 * 2 - 28;
  const H = 120;
  const PAD = 10;
  if (!values.length) return null;
  const max = Math.max(1, ...values);
  const stepX = values.length > 1 ? (width - PAD * 2) / (values.length - 1) : 0;
  const pts = values.map((v, i) => [
    PAD + i * stepX,
    H - PAD - 12 - (v / max) * (H - PAD * 2 - 22),
  ]);
  let d = `M ${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 1; i < pts.length; i++) {
    const mx = ((pts[i - 1][0] + pts[i][0]) / 2).toFixed(1);
    const my = ((pts[i - 1][1] + pts[i][1]) / 2).toFixed(1);
    d += ` Q ${pts[i - 1][0].toFixed(1)},${pts[i - 1][1].toFixed(1)} ${mx},${my}`;
  }
  const last = pts[pts.length - 1];
  d += ` L ${last[0].toFixed(1)},${last[1].toFixed(1)}`;
  const area = `${d} L ${last[0].toFixed(1)},${H - PAD} L ${pts[0][0].toFixed(1)},${H - PAD} Z`;
  const peakIdx = values.indexOf(max);
  const showLabel = (i) => i === 0 || i === values.length - 1 || i === Math.floor(values.length / 2);
  return (
    <Svg width={width} height={H}>
      <Line x1={PAD} y1={H - PAD} x2={width - PAD} y2={H - PAD} stroke={colors.border} strokeWidth={1} />
      <Path d={area} fill={accent} opacity={0.18} />
      <Path d={d} fill="none" stroke={accent} strokeWidth={2.5} strokeLinejoin="round" strokeLinecap="round" />
      {pts.map(([x, y], i) => (
        <Circle key={i} cx={x} cy={y} r={i === peakIdx && max > 0 ? 4 : 1.6} fill={accent} opacity={i === peakIdx ? 1 : 0.55} />
      ))}
      {pts.map(([x], i) =>
        showLabel(i) ? (
          <SvgText key={`l${i}`} x={x} y={H - 1} fontSize={9} fill={colors.sub} textAnchor="middle">
            {i + 1}
          </SvgText>
        ) : null,
      )}
      <SvgText x={width - PAD} y={PAD + 2} fontSize={10} fill={colors.sub} textAnchor="end">
        {`max ${max}/day`}
      </SvgText>
    </Svg>
  );
}
