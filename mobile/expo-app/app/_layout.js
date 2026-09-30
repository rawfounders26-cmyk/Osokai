import { Tabs } from 'expo-router';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { StatusBar, StyleSheet } from 'react-native';
import { useEffect } from 'react';
import { colors } from '../src/services/theme';
import { startSync } from '../src/services/api';
import HomeBar from '../src/components/HomeBar';

export default function RootLayout() {
  useEffect(() => { startSync(); }, []);
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
      <GestureHandlerRootView style={gh.root}>
        <Tabs
          initialRouteName="index"
          screenOptions={{ headerShown: false }}
          tabBar={props => <HomeBar {...props} />}
        >
          <Tabs.Screen name="dashboard" options={{ title: 'HOME' }} />
          <Tabs.Screen name="history" options={{ title: 'History' }} />
          <Tabs.Screen name="files" options={{ title: 'Files' }} />
          <Tabs.Screen name="settings" options={{ title: 'Settings & Connect' }} />
          <Tabs.Screen name="index" options={{ title: 'Chat' }} />
        </Tabs>
      </GestureHandlerRootView>
    </SafeAreaProvider>
  );
}

const gh = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
});
