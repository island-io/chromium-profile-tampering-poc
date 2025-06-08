function updateTitle(tabIndex) {
  if (typeof tabIndex === "undefined") {
    return;
  }
  if (typeof window.lastTitle === "undefined" || document.title != window.lastTitle) {
    // Title has never been adjusted or has been changed by something other than this script.
    window.originalTitle = document.title;
    setTitle(document.title, tabIndex);
  } else if (tabIndex != window.lastTabIndex) {
    // Tab index has changed; reuse last title.
    setTitle(window.originalTitle, tabIndex);
  }
}

function setTitle(title, tabIndex) {
  var prefix = tabIndex < 8 ? (tabIndex + 1) + ' ' : '';
  document.title = prefix + title + ' <' + location.host + '>';
  window.lastTitle = document.title;
  window.lastTabIndex = tabIndex;
}

function registerListener() {
  // Listen for changes from service_worker.js.
  chrome.runtime.onMessage.addListener(
    function(request, sender, sendResponse) {
      updateTitle(request.tabIndex);
    });

  // Listen for changes to the title originating from within the page.
  var titleObserver = new MutationObserver(function(mutations) {
    updateTitle(window.lastTabIndex);
  });
  
  var config = { attributes: true, childList: true, characterData: true };
  titleObserver.observe(document.getElementsByTagName('title')[0], config);
}

document.addEventListener("DOMContentLoaded", function(event) {
  registerListener();
});
