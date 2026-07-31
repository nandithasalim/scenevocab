console.log("[vocab-builder] content script loaded on Netflix");
let capturedLines = [];
let lastLine = "";

function findCaptionContainer() {
  return document.querySelector(".player-timedtext");
}

function startWatching() {
  const container = findCaptionContainer();

  if (!container) {
    // captions aren't on screen yet (video not playing) - check again in 2 seconds
    setTimeout(startWatching, 2000);
    return;
  }

  console.log("[vocab-builder] found caption container, watching for changes");

  const observer = new MutationObserver(() => {
    const text = container.innerText.trim();

    if (text && text !== lastLine) {
      lastLine = text;
      const video = document.querySelector("video");
      const timestamp = video ? video.currentTime : 0;

      capturedLines.push({ text: text, time: timestamp });
      console.log("[vocab-builder] captured:", text, "at", timestamp);
    }
  });

  observer.observe(container, { childList: true, subtree: true, characterData: true });
}

function sendTranscript() {
  if (capturedLines.length === 0) {
    return;
  }

  fetch("https://scenevocab.onrender.com/transcript", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_title: document.title,
      segments: capturedLines
    })
  })
    .then(response => response.json())
    .then(data => {
      console.log("[vocab-builder] server responded:", data);
    })
    .catch(error => {
      console.warn("[vocab-builder] failed to reach server:", error);
    });

  capturedLines = [];
}

function watchForVideoEnd() {
  const video = document.querySelector("video");

  if (video && !video.dataset.vocabListenerAdded) {
    video.addEventListener("ended", sendTranscript);
    video.dataset.vocabListenerAdded = "true";
  }

  setTimeout(watchForVideoEnd, 3000);
}
// Flush whenever the tab becomes hidden (switching tabs, minimizing, etc.)
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    sendTranscript();
  }
});

// Flush right before the page/tab actually closes
window.addEventListener("beforeunload", () => {
  sendTranscript();
});

// Safety net: flush every 5 minutes regardless, in case none of the above catch it
setInterval(() => {
  sendTranscript();
}, 5 * 60 * 1000);

function checkForExit() {
  const newPath = location.pathname;
  if (isWatchPage(lastPath) && newPath !== lastPath) {
    console.log("[vocab-builder] left previous watch page, flushing transcript");
    sendTranscript();
  }
  lastPath = newPath;
}

startWatching();
watchForVideoEnd();
checkForExit();