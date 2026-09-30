// Mic button, isolated: audio native failures must never crash Chat.
import { useState } from 'react';
import { TouchableOpacity, Text, StyleSheet } from 'react-native';
import { useAudioRecorder, useAudioRecorderState, RecordingPresets, requestRecordingPermissionsAsync } from 'expo-audio';
import { voiceTranscribe } from '../services/api';
import { colors } from '../services/theme';

export default function MicButton({ onText }) {
  const recorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recState = useAudioRecorderState(recorder);
  const recording = recState?.isRecording ?? false;
  const [busy, setBusy] = useState(false);

  const press = async () => {
    if (busy) return;
    setBusy(true);
    try {
      if (recording) {
        await recorder.stop();
        const uri = recorder.uri;
        if (uri) {
          const t = await voiceTranscribe(uri);
          if (t) onText(t);
        }
      } else {
        const perm = await requestRecordingPermissionsAsync();
        if (!perm.granted) return;
        await recorder.prepareToRecordAsync();
        recorder.record();
      }
    } catch {
    } finally {
      setBusy(false);
    }
  };

  return (
    <TouchableOpacity style={[m.send, recording && m.recOn]} onPress={press}>
      <Text style={m.sendI}>{recording ? '■' : '🎙'}</Text>
    </TouchableOpacity>
  );
}

const m = StyleSheet.create({
  send: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  recOn: { backgroundColor: colors.error },
  sendI: { color: '#fff', fontSize: 20, fontWeight: '700' },
});
