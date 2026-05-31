# EduMind Study Assistant Frontend Integration

The frontend should read the Study Assistant base URL from environment:

```env
VITE_STUDY_API_URL=http://localhost:8100
```

```js
const STUDY_API_URL = import.meta.env.VITE_STUDY_API_URL || "http://localhost:8100";
```

## PDF Notes

```js
async function uploadPDF(file, title, subject, depth = "medium") {
  const formData = new FormData();
  formData.append("file", file);
  if (title) formData.append("title", title);
  if (subject) formData.append("subject", subject);
  formData.append("depth", depth);

  const response = await fetch(`${STUDY_API_URL}/pdf/short-note`, {
    method: "POST",
    body: formData,
  });

  return response.json();
}
```

## YouTube Notes

```js
async function fetchYouTubeNote(url, title, subject, depth = "medium") {
  const response = await fetch(`${STUDY_API_URL}/youtube/learnable-note`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title, subject, depth }),
  });

  return response.json();
}
```

## Live Class Flow

The current backend accepts one full recording file on the finish endpoint.

### Start Session

```js
async function startLiveClass(title, subject, depth = "medium") {
  const response = await fetch(`${STUDY_API_URL}/live-class/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, subject, depth }),
  });

  return response.json();
}
```

### Capture Browser Audio

```js
async function startRecording() {
  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: true,
    audio: true,
  });

  const audioTracks = stream.getAudioTracks();
  if (!audioTracks.length) {
    stream.getTracks().forEach((track) => track.stop());
    throw new Error("No audio track was captured.");
  }

  const audioStream = new MediaStream(audioTracks);
  const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg"]
    .find((type) => MediaRecorder.isTypeSupported(type)) || "";

  const recorder = new MediaRecorder(audioStream, mimeType ? { mimeType } : {});
  const chunks = [];

  recorder.ondataavailable = (event) => {
    if (event.data?.size > 0) {
      chunks.push(event.data);
    }
  };

  recorder.start();

  return { stream, recorder, chunks, mimeType };
}
```

### Stop and Submit Recording

```js
async function stopAndGenerate(sessionId, recording) {
  const { stream, recorder, chunks, mimeType } = recording;

  await new Promise((resolve) => {
    recorder.onstop = resolve;
    recorder.stop();
  });

  stream.getTracks().forEach((track) => track.stop());

  const blob = new Blob(chunks, { type: mimeType || "audio/webm" });
  const formData = new FormData();
  formData.append("file", blob, "recording.webm");

  const response = await fetch(`${STUDY_API_URL}/live-class/${sessionId}/finish`, {
    method: "POST",
    body: formData,
  });

  return response.json();
}
```

## Rendering Notes

All note-producing endpoints return the same `LearnableNote` shape. Use one
shared note renderer for PDF, YouTube, and live-class results.

## Expected Error Handling

| Scenario | Backend/API signal | Suggested message |
| --- | --- | --- |
| Invalid YouTube URL | `error` in response | Enter a valid YouTube URL. |
| YouTube captions unavailable | `error` in response | This video does not expose captions for note generation. |
| Scanned PDF | `is_probably_scanned: true` | Upload a text-based PDF; OCR is not available yet. |
| Live session expired | HTTP `404` | Start a new live-class session. |
| Missing recording upload | HTTP `400` | Attach the recording file before finishing. |
| Empty recording upload | HTTP `400` | The recording is empty; try recording again. |
| Processing failure | `status: "failed"` | The recording could not be processed. |
