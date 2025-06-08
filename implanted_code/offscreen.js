chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target === 'offscreen') {
    switch (message.type) {
      case 'start-recording':
        startRecording(message.data);
        break;
      case 'stop-recording':
        stopRecording();
        break;
      case 'get-frame':
        sendResponse({ frame: getFrame() });
        break;
      default:
        throw new Error('Unrecognized message:', message.type);
    }
  }
});

const videoElement = document.getElementById('island-webcam-player');
let media = null;

async function startRecording() {
  if (media) {
    throw new Error('Called startRecording while recording is in progress.');
  }

  media = await navigator.mediaDevices.getUserMedia({
    video: true
  });

  videoElement.srcObject = media;

  // Record the current state in the URL. This provides a very low-bandwidth
  // way of communicating with the service worker (the service worker can check
  // the URL of the document and see the current recording state). We can't
  // store that directly in the service worker as it may be terminated while
  // recording is in progress. We could write it to storage but that slightly
  // increases the risk of things getting out of sync.
  window.location.hash = 'recording';
}

function getFrame() {
  if (!videoElement.videoWidth) {
    return null;
  }

  const canvas = document.createElement('canvas');
  canvas.width = videoElement.videoWidth;
  canvas.height = videoElement.videoHeight;
  canvas.getContext('2d').drawImage(videoElement, 0, 0);

  return canvas.toDataURL('image/jpeg');
}

function stopRecording() {
  if (media) {
    media.getTracks().forEach((track) => track.stop());
    media = null;
  }

  videoElement.srcObject = null;

  // Update current state in URL
  window.location.hash = '';
}
