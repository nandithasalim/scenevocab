chrome.storage.local.get(["vocabUserId"], (result) => {
    const userId = result.vocabUserId || crypto.randomUUID();
    chrome.storage.local.set({ vocabUserId: userId });
  
    document.getElementById("open-btn").addEventListener("click", () => {
      chrome.tabs.create({
        url: `https://scenevocab-frontend-jpccjv4ug-nandithasalims-projects.vercel.app?uid=${userId}`
      });
      window.close();
    });
  });