// Osok-AI connection config — Backend URL + Auth Token, persisted on device.
import AsyncStorage from '@react-native-async-storage/async-storage';

const KEYS = { SERVER_URL: 'OSOKAI_base', AUTH_TOKEN: 'OSOKAI_token', DEVICE: 'OSOKAI_device' };
const LAN_DEFAULT = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://10.248.214.177:8765';

export async function loadConfig() {
  try {
    const [url, token, device] = await AsyncStorage.multiGet([KEYS.SERVER_URL, KEYS.AUTH_TOKEN, KEYS.DEVICE]);
    return {
      serverUrl: url[1] || LAN_DEFAULT,
      authToken: token[1] || '',
      device: device[1] || 'mobile-app',
    };
  } catch {
    return { serverUrl: LAN_DEFAULT, authToken: '', device: 'mobile-app' };
  }
}

export async function saveConfig(cfg) {
  const pairs = [];
  if (cfg.serverUrl !== undefined) pairs.push([KEYS.SERVER_URL, cfg.serverUrl]);
  if (cfg.authToken !== undefined) pairs.push([KEYS.AUTH_TOKEN, cfg.authToken]);
  if (cfg.device !== undefined) pairs.push([KEYS.DEVICE, cfg.device]);
  await AsyncStorage.multiSet(pairs);
}
