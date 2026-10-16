---
name: Bug report
about: Something is broken or behaves wrong
title: ''
labels: bug
assignees: ''
---

**Describe the bug**
A clear and concise description of what the bug is.

**To reproduce**
Steps to reproduce the behaviour:
1. Start NetSpeedTray …
2. …
3. …

**Expected behaviour**
What you expected to happen instead.

**Environment**
- NetSpeedTray version (right-click menu header, or `NetSpeedTray.exe --version`):
- Windows version:
- Running the `.exe` or from source:
- Single or multi monitor (and which monitor the card sits on):

**Log file**
Attach the log at `%APPDATA%\NetSpeedTray\netspeedtray.log`
(created on the next launch after the problem). The key line to check is
`startup: launched` — its absence after a reboot means Windows never started
the app (see README ▸ Troubleshooting).
