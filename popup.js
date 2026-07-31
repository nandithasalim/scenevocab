document.getElementById("open-btn").addEventListener("click", () => {
    chrome.tabs.create({ url: "https://scenevocab-frontend-jpccjv4ug-nandithasalims-projects.vercel.app" });
    window.close();
  });