import { useEffect, useRef } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Animated } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { MonthFolderShape, accentForMonth, inkForAccent, shortLabel } from './MonthFolder';

// Horizontal step between stacked folders + swipe threshold physics.
const STEP_X = 108;
const SWIPE_DIST = 60;
const SWIPE_VEL = 550;

export function FolderStack({ months, front, onFrontChange, onOpen, locked }) {
  const frontIdx = Math.max(0, months.findIndex(m => m.month === front));
  const pos = useRef(new Animated.Value(frontIdx)).current;
  const dragX = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.spring(pos, { toValue: frontIdx, useNativeDriver: true, damping: 22, stiffness: 220 }).start();
  }, [frontIdx, pos]);

  const settleDrag = (toFront) => {
    if (toFront !== frontIdx) {
      Animated.timing(dragX, { toValue: 0, duration: 160, useNativeDriver: true }).start();
      onFrontChange(months[toFront].month);
    } else {
      Animated.spring(dragX, { toValue: 0, useNativeDriver: true, damping: 20, stiffness: 260 }).start();
    }
  };

  const pan = Gesture.Pan()
    .enabled(!locked && months.length > 1)
    .activeOffsetX([-14, 14])
    .onUpdate(e => dragX.setValue(e.translationX))
    .onEnd(e => {
      const dx = e.translationX;
      const vx = e.velocityX;
      let target = frontIdx;
      if (dx < -SWIPE_DIST || vx < -SWIPE_VEL) target = Math.min(frontIdx + 1, months.length - 1);
      else if (dx > SWIPE_DIST || vx > SWIPE_VEL) target = Math.max(frontIdx - 1, 0);
      settleDrag(target);
    });

  if (!months.length) return null;

  return (
    <GestureDetector gesture={pan}>
      <View style={fs.stage}>
        {months.map((m, i) => {
          const off = Animated.subtract(Animated.subtract(pos, Animated.divide(dragX, STEP_X)), i);
          const depth = off.interpolate({
            inputRange: [-2, 0, 2], outputRange: [-2, 0, 2], extrapolate: 'clamp',
          });
          const translateX = Animated.multiply(depth, -STEP_X);
          const scale = depth.interpolate({ inputRange: [-2, 0, 2], outputRange: [0.9, 1, 0.9] });
          const opacity = depth.interpolate({
            inputRange: [-2.5, -1, 0, 1, 2.5], outputRange: [0.2, 0.55, 1, 0.55, 0.2],
          });
          const rotate = depth.interpolate({
            inputRange: [-2, 0, 2], outputRange: ['-2deg', '0deg', '2deg'],
          });
          const a = accentForMonth(months, m.month);
          const ink = inkForAccent(a);
          const order = months.length - Math.abs(i - frontIdx);
          return (
            <Animated.View
              key={m.month}
              style={[fs.card, { transform: [{ translateX }, { scale }, { rotate }], opacity, zIndex: order, elevation: order }]}
            >
              <TouchableOpacity onPress={() => onOpen(m.month)} activeOpacity={0.92}>
                <MonthFolderShape color={a} />
                <View style={fs.caption}>
                  <Text style={[fs.label, { color: ink }]}>{shortLabel(m.month)}</Text>
                  <Text style={[fs.meta, { color: ink }]}>
                    {(m.tasks ?? 0)} goal{((m.tasks ?? 0) !== 1) ? 's' : ''}
                  </Text>
                </View>
              </TouchableOpacity>
            </Animated.View>
          );
        })}
      </View>
    </GestureDetector>
  );
}

const fs = StyleSheet.create({
  stage: { height: 400 },
  card: {
    position: 'absolute', top: 8, left: 8, right: 8,
    shadowColor: '#000', shadowOpacity: 0.4, shadowRadius: 10,
    shadowOffset: { width: 0, height: 6 },
  },
  caption: {
    position: 'absolute', left: 30, right: 26, top: 104,
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
  },
  label: { fontSize: 24, fontWeight: '800' },
  meta: { fontSize: 13, fontWeight: '700', opacity: 0.9 },
});
