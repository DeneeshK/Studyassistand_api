# EduMind Study Assistant — Frontend Integration Guide

---

## Study API base URL

The frontend reads `VITE_STUDY_API_URL` from its `.env` file:

```env
VITE_STUDY_API_URL=http://localhost:8100
```

In component code:
```js
const STUDY_API_URL = import.meta.env.VITE_STUDY_API_URL || "http://localhost:8100";
```

---

## PDF Notes — sample call

```js
async function uploadPDF(file, title, subject, depth = "medium") {
  const formData = new FormData();
  formData.append("file", file);
  if (title)   formData.append("title", title);
  if (subject) formData.append("subject", subject);
  formData.append("depth", depth);

  const res = await fetch(`${STUDY_API_URL}/pdf/short-note`, {
    method: "POST",
    body: formData,
  });
  return res.json();
}
```

---

## YouTube Notes — sample call

```js
async function fetchYouTubeNote(url, title, subject, depth = "medium") {
  const res = await fetch(`${STUDY_API_URL}/youtube/learnable-note`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title, subject, depth }),
  });
  return res.json();
}
```

---

## Google Meet / Live Class — full capture flow

### 1. Start session

```js
const res = await fetch(`${STUDY_API_URL}/live-class/start`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ title: "Chapter 5", subject: "Physics" }),
});
const { session_id } = await res.json();
```

### 2. Request tab capture (browser native popup)

```js
async function startMeetCapture(sessionId) {
  // Browser shows native tab-sharing picker
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: true,   // required by browsers; video track is discarded
    audio: true,
  });

  // Validate audio
  const audioTracks = stream.getAudioTracks();
  if (!audioTracks.length) {
    stream.getTracks().forEach(t => t.stop());
    throw new Error(
      "No audio was captured. Select a Chrome Tab and enable 'Share tab audio'."
    );
  }

  // Audio-only stream
  const audioStream = new MediaStream(audioTracks);

  // Pick best supported MIME type
  const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"]
    .find(m => MediaRecorder.isTypeSupported(m)) || "";

  const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : {});

  recorder.ondataavailable = async (event) => {
    if (event.data?.size > 0) {
      const formData = new FormData();
      formData.append("file", event.data, `chunk-${Date.now()}.webm`);
      await fetch(`${STUDY_API_URL}/live-class/${sessionId}/audio-chunk`, {
        method: "POST",
        body: formData,
      });
    }
  };

  recorder.start(5000); // upload every 5 seconds

  return { stream, recorder };
}
```

### 3. Stop and get notes

```js
async function stopAndFinish(sessionId, recorder, stream) {
  // Stop recorder and wait for final chunk
  await new Promise(resolve => {
    recorder.onstop = resolve;
    recorder.stop();
  });

  // Release browser tracks
  stream.getTracks().forEach(t => t.stop());

  // Ask backend to transcribe and generate note
  const res = await fetch(`${STUDY_API_URL}/live-class/${sessionId}/finish`, {
    method: "POST",
  });
  return res.json(); // { session_id, status, transcript, note, error }
}
```

---

## Instructions UI text

Show this to the user before they click Start:

```
1. Open your Google Meet in a separate tab.
2. Come back to EduMind.
3. Click "Start Live Assistant".
4. In the browser popup, choose Chrome Tab.
5. Select your Google Meet tab.
6. Make sure "Share tab audio" is checked.
7. Do NOT select this EduMind tab.
8. Click Share.
```

---

## Error handling

| Scenario | `err.name` / response field | User-friendly message |
|---|---|---|
| User cancelled the sharing popup | `NotAllowedError` | "Screen sharing was cancelled. Please try again." |
| No audio track returned | — | "No audio captured. Select a Tab and enable Share tab audio." |
| Session not found (backend) | `error` in JSON | "Session expired. Please start a new session." |
| Transcription returned empty | `error` in JSON | "No speech was detected in the recording." |
| ffmpeg missing | `error` in JSON | "Server configuration error — ffmpeg not installed." |

---

## Rendering the note

All three endpoints return the same note shape. Use a shared `<NoteDisplay note={note} />`
component. See `LiveClassAssistant.jsx` for a complete example with sections, flashcards,
practice questions, and MCQs.
