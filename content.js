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
    if (text) {
      console.log("[vocab-builder] captured:", text);
    }
  });

  observer.observe(container, { childList: true, subtree: true, characterData: true });
}

startWatching();