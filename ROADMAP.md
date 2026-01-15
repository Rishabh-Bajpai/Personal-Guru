# Roadmap

We believe in building in public. This roadmap outlines our current priorities and future plans for **Personal Guru**.

> **Note**: This roadmap is a living document and subject to change based on community feedback and new discoveries.

## 🚀 In Progress

These items are actively being worked on by the core team.

- **Windows Compatibility**: Fixing code execution environments for Windows users.
- **Mode Demos**: Creating comprehensive demonstration videos/guides for each learning mode (Chat, Chapter, Quiz, Flashcard, Reel).

## 📋 Ready for Development

These features are specified and ready to be picked up. Contributions are welcome!

- **Telemetry Enhancements**:
  - Add `user_id` to telemetry logs for better data correlation.
  - Allow feedback submission without requiring login (for guest users).
- **Data Collection Server (DCS) Improvements**:
  - Resolve sync issues between client and server.
  - Add `installation` table to track machine info for synced devices.
- **Database & Architecture**:
  - **Prompt Optimization**: Update prompts to prevent "Chapter Mode" step names exceeding 255 characters.
  - **Roadmap**: Publish project roadmap (Done! ✅).
- **Tooling**:
  - **Auto-Update**: Create a tool for automatic application updates and notification system.

## 📅 Backlog (Planned)

Future features and improvements on our radar.

### Core Features

- **Multi-Device Sync**: Robust synchronization across different devices.
- **User Authentication**: Enhanced auth flows including multi-device support.
- **Course Progress**: improved persistence and resume functionality for long courses.

### Learning Modes

- **Reel Mode**:
  - Integration with Study Plans.
  - UI/UX improvements for better engagement.
- **Learning History**: A dedicated database/view for tracking comprehensive learning history.

### Documentation

- **Development Guide**: extensive guide for contributors (Started in `CONTRIBUTING.md`).

## ✅ Recently Completed

- **Project Structure**: Created `CONTRIBUTING.md`, `SECURITY.md`, and Issue Templates.
- **Website**: Launched documentation website.
- **Installation**: Simplified installation and deployment scripts.
- **Chat Mode**: Improved auto-scroll behavior (scroll to start of new message).
- **Flashcards/Quiz**: Added ability to select custom number of items to generate.
- **Stability**: improved overall exception handling.

---

**Have a suggestion?** Open a [Feature Request](https://github.com/Rishabh-Bajpai/Personal-Guru/issues/new?template=feature_request.md) to discuss it!
