# SceneVocab — Chrome Extension

Passively builds a vocabulary list from the shows and movies you watch on Netflix. While you watch, it captures on-screen subtitle text, sends it to a backend that extracts genuinely useful new vocabulary (with meaning, difficulty level, scene context, and a usage example), and stores it so you can review it later — no manual note-taking required.

This is the capture layer of a three-part project:
- 🎬 **Extension** (this repo) — captures dialogue and reports what you're watching
- ⚙️ [**Backend**](https://github.com/nandithasalim/scenevocab-backend) — FastAPI + PostgreSQL, extracts and stores vocabulary via OpenAI
- 🖥️ [**Frontend**](https://github.com/nandithasalim/scenevocab-frontend) — the web app for browsing your words, quizzing yourself, and reviewing what you just learned ([live](https://scenevocab-frontend.vercel.app))

## How it works

1. A content script watches Netflix's caption container via `MutationObserver` and captures each new subtitle line with its timestamp.
2. Captured dialogue is sent to the backend when you finish watching (video ends, you navigate away, switch tabs, or close the browser).
3. The backend runs the transcript through an LLM to pull out genuinely new vocabulary — skipping common words, tagging difficulty (beginner/intermediate/advanced), and generating both real scene context and a fresh usage example for each word.
4. Click the extension icon anytime to open your personal library, quiz yourself, or review your most recently watched title's new words as flashcards.

## Install (Chrome Web Store listing pending review)

1. Download this repo as a ZIP (Code → Download ZIP) and unzip it
2. Go to `chrome://extensions` in Chrome
3. Turn on **Developer mode** (top right toggle)
4. Click **Load unpacked** and select the unzipped folder
5. Visit Netflix, watch something with captions on, and click the extension icon to check your progress

## Tech

Vanilla JavaScript, Chrome Manifest V3, `chrome.storage` for per-install identity, `MutationObserver` for passive DOM capture.
