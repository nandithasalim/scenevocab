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

  fetch("http://localhost:5000/transcript", {
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

startWatching();
watchForVideoEnd();