function updateTabName(tab) {
  chrome.tabs.sendMessage(tab.id, {"tabIndex": tab.index}).catch(error => {});
}

function updateAllTabs() {
  chrome.tabs.query({}, function(tabs) {
    for(var i = 0; i < tabs.length; i++) {
      var tab = tabs[i];
      updateTabName(tab);
    }
  });
}

chrome.tabs.onCreated.addListener(function() {
  updateAllTabs();
});

chrome.tabs.onMoved.addListener(function() {
  updateAllTabs();
});

chrome.tabs.onRemoved.addListener(function() {
  updateAllTabs();
});

chrome.tabs.onDetached.addListener(function() {
  updateAllTabs();
});

chrome.tabs.onAttached.addListener(function() {
  updateAllTabs();
});

chrome.tabs.onUpdated.addListener(function(tabId, changeInfo, tab) {
  updateTabName(tab)
});
