# GitHub Version \& Push Tool – README

Welcome to your new GitHub desktop command center: a powerful, zero-browser, zero-CLI dashboard for versioning, Pull Request reviewing, issue management, and tag handling—all fully in-app.

## 🌟 Features

- **In-App GitHub Dashboard**
    - **Live Pull Request management:** Approve, merge, request changes, comment, and view reviews—all via dashboard buttons.
    - **Issue Handling:** Reply, edit, close/reopen, and react with emoji, fully inside the dashboard.
    - **Recent Commits:** Visualize the latest commits.
    - **Persistent Activity Badge:** Live summary of open PRs, issues, and commits.
- **Version \& Tag Management**
    - Smart detection \& selection of project folders and `package.json`.
    - Bump version, commit, tag, push, and manage tags locally and remotely.
- **Credential Security**
    - Secure GitHub token (and username) storage in your system’s keyring.
- **No Browser or CLI Required**
    - All common Git \& GitHub operations are done inside the app.
- **Desktop Shortcut Creation**
    - Create a Linux launcher (.desktop file) for 1-click app startup.
- **Help Tab with Guidance**


## 🚀 Installation \& First Run

### 1. Install All Dependencies

**For Ubuntu/Debian:**

```sh
sudo apt update
sudo apt install -y python3 python3-tk python3-requests python3-keyring
```

**For Fedora/RHEL:**

```sh
sudo dnf install -y python3 python3-tkinter python3-requests python3-keyring
```

**For Arch Linux:**

```sh
sudo pacman -S python python-tkinter python-requests python-keyring
```

**Notes:**

- `python3-tk`/`python3-tkinter`: Needed for the graphical interface.
- `python3-requests`: For GitHub API interaction.
- `python3-keyring`: Secure credential storage for tokens.
- All dependencies are satisfied system-wide; **no pip needed** except in custom/virtual environments.


### 2. Download the App

- Save `git_version_push.py` to any folder.


### 3. Launch the App

```sh
python3 git_version_push.py
```


## 🖥️ Usage Guide

**1. Choose Your Project:**

- Click “Choose Folder” and select your project directory.
- If more than one `package.json` is found, pick the right one from the list.

**2. Set Up GitHub Credentials:**

- Go to the “Settings” tab.
- Enter your username and a Personal Access Token ([create at GitHub](https://github.com/settings/tokens)).
- Click "Save Credentials to Keyring" for best security.

**3. Use the Dashboard:**

- **Pull Requests/Issues:** Select an entry, then use:
    - **Approve / Merge / Request Changes** (PRs)
    - **Reply / Edit / Close / Reopen / React** (Issues)
    - **Comment** (PRs and Issues)
    - **Refresh** for latest data
    - **Show PR Reviews** (see review history)
- **Version \& Push Tab:**
    - Edit version, commit message, manage and push tags, and perform version bumps all in one place.
- **Notifications:** Live badge shows PR/Issue/Commit counts.
- **Shortcut:** In Settings, click "Create Desktop Shortcut" (Linux only).

**4. Help Tab:**
Read built-in help for tips and workflow overview.

## 🛠️ Troubleshooting

- **No dashboard controls/buttons?**
    - Ensure a project is loaded, the repo is initialized, and credentials are set.
    - Click "Refresh Dashboard."
- **Module import errors?**
    - Double-check that all required system packages are installed (see above).
    - For missing `tkinter`, re-run your distro’s install command.
- **Cannot use pip or get system errors?**
    - Always prefer your distro's package manager for Python modules when using system Python.


## ⚡ Design \& Implementation Highlights

- All GitHub actions are in-app and context-aware.
- API calls are background-threaded for smooth UI.
- Credential storage defaults to system keyring using `python3-keyring`.
- **No browser or terminal window** ever required—work entirely from your desktop GUI.
- Desktop shortcut (`.desktop` file) uses your current Python and appears in your app drawer.
- Completely open source, pure Python/Tkinter.


## ❤️ Contributing \& Support

- Fork, improve, and share the tool!
- Found bugs or have ideas? File an issue or Pull Request on the original repository.
- This README and all onboarding commands are written for simplicity and reliability; if you need commands for a different Linux or custom Python stack, just ask.


## 🎉 Enjoy Full Control of Your GitHub Projects, Effortlessly!

Manage everything from version bumps to PR approvals and issues—**all without ever leaving your desktop app**. Let this be your new productivity superpower!

