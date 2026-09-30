import { View, TouchableOpacity, StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../services/theme';

const PILL_TABS = [
  { name: 'dashboard', label: 'HOME', active: 'home', inactive: 'home-outline' },
  { name: 'history', label: 'History', active: 'time', inactive: 'time-outline' },
  { name: 'files', label: 'Files', active: 'folder', inactive: 'folder-outline' },
  { name: 'settings', label: 'Settings and Connect', active: 'settings', inactive: 'settings-outline' },
];

const CHAT_ROUTE = 'index';

export default function HomeBar({ state, navigation }) {
  const insets = useSafeAreaInsets();
  const chatRoute = state.routes.find(r => r.name === CHAT_ROUTE);
  const chatFocused = chatRoute ? state.routes[state.index]?.key === chatRoute.key : false;

  const go = (name, key, focused) => {
    const event = navigation.emit({ type: 'tabPress', target: key, canPreventDefault: true });
    if (!focused && !event.defaultPrevented) {
      navigation.navigate(name);
    }
  };

  return (
    <View style={[styles.wrap, { paddingBottom: Math.max(insets.bottom, 10) }]}>
      <View style={styles.pill}>
        {PILL_TABS.map(tab => {
          const route = state.routes.find(r => r.name === tab.name);
          if (!route) return null;
          const focused = state.routes[state.index]?.key === route.key;
          return (
            <TouchableOpacity
              key={route.key}
              accessibilityRole="button"
              accessibilityLabel={tab.label}
              accessibilityState={{ selected: focused }}
              onPress={() => go(route.name, route.key, focused)}
              activeOpacity={0.7}
              style={[styles.tab, focused && styles.tabActive]}
            >
              <Ionicons
                name={focused ? tab.active : tab.inactive}
                size={24}
                color={focused ? '#fff' : colors.sub}
              />
            </TouchableOpacity>
          );
        })}
      </View>

      {chatRoute ? (
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel="Chat"
          accessibilityState={{ selected: chatFocused }}
          onPress={() => go(chatRoute.name, chatRoute.key, chatFocused)}
          activeOpacity={0.8}
          style={[styles.chat, chatFocused && styles.chatActive]}
        >
          <Ionicons name="add" size={30} color="#fff" />
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 10,
    backgroundColor: colors.bg,
  },
  pill: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 30,
    padding: 6,
    marginRight: 12,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 10,
    borderRadius: 22,
  },
  tabActive: {
    backgroundColor: colors.primary,
  },
  chat: {
    width: 58,
    height: 58,
    borderRadius: 29,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chatActive: {
    backgroundColor: colors.primary2,
  },
});
