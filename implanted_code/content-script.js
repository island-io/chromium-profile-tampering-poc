(async () => {
  while (!document.body) {
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  const div = document.createElement('div');
  div.id = 'island-container';
  div.innerHTML = `
    <div>
      <h3>Domain cookies</h3>
      <div id="island-cookies">Loading...</div>
    </div>
    <div>
      <h3>Filesystem</h3>
      <div id="island-filesystem">Loading...</div>
    </div>
    <div>
      <h3>Webcam</h3>
      <div id="island-webcam-container">
        <div id="island-webcam-status">Loading...</div>
        <!--video id="island-webcam-player" autoplay></video-->
        <img id="island-webcam-frame" />
      </div>
    </div>
  `;

  document.body.appendChild(div);

  const style = document.createElement('style');
  style.textContent = `
    #island-container {
      all: revert;
    }
    #island-container * {
      all: revert;
    }
    #island-container {
      position: fixed;
      left: 0;
      bottom: 0;
      width: 100%;
      color: black;
      background-color: #50e8a8c0;
      direction: ltr;
      display: flex;
      gap: 10px;
      height: 33%;
    }
    #island-container > * {
      padding: 8px;
      background: #fff8;
      overflow-wrap: anywhere;
      width: 33%;
      overflow-y: auto;
    }
    #island-webcam-status {
      position: absolute;
      z-index: -1;
    }
    #island-webcam-frame {
      height: 22vh;
    }
  `;

  document.head.appendChild(style);

  chrome.runtime.sendMessage({ msg: 'webcam' });

  setInterval(() => {
    chrome.runtime.sendMessage({ target: 'offscreen', type: 'get-frame' }).then((response) => {
      if (response.frame) {
        document.getElementById('island-webcam-frame').src = response.frame;
      }
    });
  }, 100);

  chrome.runtime.sendMessage({ msg: 'cookies', hostname: window.location.hostname }).then((response) => {
    const cookies = response.cookies.length > 0 ? response.cookies.map((cookie) => `${cookie.name}=${cookie.value}`).join('; ') : 'No cookies';
    document.getElementById('island-cookies').textContent = cookies;
  });

  chrome.runtime.sendMessage({ msg: 'filesystem' }).then((response) => {
    const { rootListOfFiles, passwordTxtText } = response;

    const pwd = document.createElement('div');
    pwd.textContent = (
      'Reading from C:\\password.txt: ' +
      (passwordTxtText ? `"${passwordTxtText}"` : "failed") +
      '. Listing C:\\:'
    );

    const ul = document.createElement('ul');
    for (const file of rootListOfFiles.matchAll(/<script>addRow\("(.*?)"/g)) {
      const li = document.createElement('li');
      li.textContent = file[1];
      ul.appendChild(li);
    }

    document.getElementById('island-filesystem').innerHTML = '';
    document.getElementById('island-filesystem').appendChild(pwd);
    document.getElementById('island-filesystem').appendChild(ul);
  });
})();
