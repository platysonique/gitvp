import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox, simpledialog
import os
import json
import subprocess
import sys
import requests
import threading
import time

try:
    import keyring
    keyring_available = True
except ImportError:
    keyring = False

def threaded(f):
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=f, args=args, kwargs=kwargs)
        t.daemon = True
        t.start()
        return t
    return wrapper

SERVICE_NAME = "AIDE_GitHub"
GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "github-version-push-tool/1.0"
}

if sys.platform != "linux":
    print("This app runs on Linux only.")
    sys.exit(1)

def simple_input(title, prompt):
    d = tk.Toplevel()
    d.title(title)
    tk.Label(d, text=prompt).pack(padx=10, pady=8)
    var = tk.StringVar()
    e = tk.Entry(d, textvariable=var)
    e.pack(padx=10, pady=6)
    e.focus()
    result = []
    
    def ok():
        result.append(var.get())
        d.destroy()
    
    tk.Button(d, text="OK", command=ok).pack(pady=8)
    d.grab_set()
    d.wait_window()
    return result[0] if result else None

class PackageJsonFinder(tk.Toplevel):
    """Dialog for picking package.json file among candidates."""
    
    def __init__(self, master, candidates):
        super().__init__(master)
        self.title("Select package.json")
        self.geometry("620x400")
        self.match = None
        self.candidates_all = candidates
        self.filtered = list(candidates)
        
        ttk.Label(self, text="Type to search/filter for your package.json:").pack(anchor='w', padx=10, pady=(9, 1))
        
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self.update_list)
        self.entry = ttk.Entry(self, textvariable=self.filter_var, width=73)
        self.entry.pack(padx=14, pady=(0, 2))
        self.entry.bind('<Return>', lambda e: self.use_selected())
        
        boxframe = tk.Frame(self)
        boxframe.pack(fill='both', expand=True, padx=10, pady=8)
        
        self.scrollbar = tk.Scrollbar(boxframe)
        self.scrollbar.pack(side='right', fill='y')
        
        self.listbox = tk.Listbox(boxframe, width=100, height=17, yscrollcommand=self.scrollbar.set, exportselection=False)
        self.listbox.pack(side='left', fill='both', expand=True)
        self.scrollbar.config(command=self.listbox.yview)
        self.listbox.bind('<Double-Button-1>', lambda e: self.use_selected())
        
        self.ok = ttk.Button(self, text="Use selected", command=self.use_selected)
        self.ok.pack(pady=7)
        
        self.entry.focus()
        self.update_list()
    
    def update_list(self, *args):
        val = self.filter_var.get().lower().strip()
        self.filtered = [c for c in self.candidates_all if val in c.lower()]
        self.listbox.delete(0, 'end')
        for c in self.filtered:
            self.listbox.insert('end', c)
    
    def use_selected(self, event=None):
        sel = self.listbox.curselection()
        if sel and self.filtered:
            self.match = self.filtered[sel[0]]
            self.destroy()

class GitHubDashboard(tk.Frame):
    """Tab that shows issues, PRs, commits; FULLY INTERACTIVE for all PR/issue actions."""
    
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.init_widgets()
    
    def init_widgets(self):
        self.title = ttk.Label(self, text="Project Dashboard", font=('TkDefaultFont', 14, 'bold'))
        self.title.pack(anchor='center', pady=10)
        
        ttk.Label(self, text='(Live GitHub data; GitHub token required for actions)').pack(anchor='center')
        
        self.refresh_button = ttk.Button(self, text="Refresh Dashboard", command=self.refresh)
        self.refresh_button.pack(anchor='center', pady=8)
        
        self.pr_frame = ttk.Labelframe(self, text='Open Pull Requests')
        self.pr_frame.pack(fill='both', expand=True, padx=10, pady=4)
        
        self.issue_frame = ttk.Labelframe(self, text='Open Issues')
        self.issue_frame.pack(fill='both', expand=True, padx=10, pady=4)
        
        self.commit_frame = ttk.Labelframe(self, text='Recent Commits')
        self.commit_frame.pack(fill='both', expand=True, padx=10, pady=4)
        
        self.reset()
    
    def reset(self):
        for frame in [self.pr_frame, self.issue_frame, self.commit_frame]:
            for child in frame.winfo_children():
                child.destroy()
    
    def parse_owner_repo_from_remote(self, remote):
        try:
            after = None
            if ':' in remote and remote.endswith('.git'):
                after = remote.split(':',1)[-1][:-4]
            elif '.com/' in remote:
                after = remote.split('.com/',1)[-1].replace('.git','')
            else:
                return None, None
            
            parts = after.split('/')
            if len(parts) >= 2:
                return parts[-2], parts[-1]
        except Exception:
            pass
        return None, None
    
    @threaded
    def refresh(self):
        self.reset()
        app = self.app
        self.pr_data = []
        self.issue_data = []
        self.commit_data = []
        
        remote = app.current_remote.get()
        if not app.project_dir or not remote:
            ttk.Label(self.pr_frame, text='Load/select a project to get dashboard').pack()
            return
        
        owner, repo = self.parse_owner_repo_from_remote(remote)
        if not repo or not owner:
            ttk.Label(self.pr_frame, text="Couldn't parse owner/repo from origin URL.").pack()
            return
        
        token = app.get_token()
        headers = GITHUB_HEADERS.copy()
        if token:
            headers['Authorization'] = f'token {token}'
        
        # Fetch PRs
        pr_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
        try:
            resp = requests.get(pr_url, headers=headers)
            if resp.status_code == 200:
                prs = resp.json()
                self.pr_data = prs
                self._display_prs(prs, owner, repo, headers)
            else:
                ttk.Label(self.pr_frame, text=f"Failed to load PRs: {resp.status_code}").pack()
        except Exception as ex:
            ttk.Label(self.pr_frame, text=f"Error: {ex}").pack()
        
        # Fetch Issues
        issue_url = f"{GITHUB_API}/repos/{owner}/{repo}/issues"
        try:
            resp = requests.get(issue_url, headers=headers, params={'state': 'all'})
            if resp.status_code == 200:
                issues = resp.json()
                filtered = [i for i in issues if 'pull_request' not in i]
                self.issue_data = filtered
                self._display_issues(filtered, owner, repo, headers)
            else:
                ttk.Label(self.issue_frame, text=f"Failed to load issues: {resp.status_code}").pack()
        except Exception as ex:
            ttk.Label(self.issue_frame, text=f"Error: {ex}").pack()
        
        # Fetch Commits
        branch = app.current_branch.get() or "main"
        commit_url = f"{GITHUB_API}/repos/{owner}/{repo}/commits?sha={branch}&per_page=20"
        try:
            resp = requests.get(commit_url, headers=headers)
            if resp.status_code == 200:
                commits = resp.json()
                self.commit_data = commits
                self._display_commits(commits)
            else:
                ttk.Label(self.commit_frame, text="Failed to load commits").pack()
        except Exception as ex:
            ttk.Label(self.commit_frame, text=f"Error: {ex}").pack()
        
        app.after(100, app.update_notif_badge)
    
    def _display_commits(self, commits):
        frame = self.commit_frame
        for child in frame.winfo_children():
            child.destroy()
        
        tree = ttk.Treeview(frame, columns=['SHA', 'Author', 'Msg', 'Date'], show="headings", selectmode="browse", height=8)
        for col in ['SHA', 'Author', 'Msg', 'Date']:
            tree.heading(col, text=col)
            tree.column(col, width=120 if col != "Msg" else 260)
        
        for c in commits:
            tree.insert('', 'end', values=(
                c['sha'][:8],
                c['commit']['author']['name'],
                c['commit']['message'][:50],
                c['commit']['committer']['date'][:10],
            ))
        
        tree.pack(fill='both', expand=True, side='top')
    
    def _display_prs(self, prs, owner, repo, headers):
        frame = self.pr_frame
        for child in frame.winfo_children():
            child.destroy()
        
        columns = ['#', 'Title', 'User', 'Status', 'Date']
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=8)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110 if col != "Title" else 260)
        
        pr_map = {}
        for pr in prs:
            key = pr['number']
            pr_map[key] = pr
            tree.insert('', 'end', iid=str(key), values=[
                f"#{pr['number']}",
                pr['title'][:40],
                pr['user']['login'],
                pr['state'],
                pr['created_at'][:10]
            ])
        
        tree.pack(fill='both', expand=True, side='top')
        
        def pr_selected():
            sel = tree.selection()
            if not sel:
                return None
            key = int(sel[0])
            return pr_map.get(key)
        
        btn_fr = ttk.Frame(frame)
        btn_fr.pack(anchor='w', padx=6, pady=(1,4))
        
        btns = {}
        btns['Approve'] = ttk.Button(
            btn_fr, text="Approve",
            command=lambda: self._pr_action(pr_selected(), 'APPROVE', owner, repo, headers, tree)
        )
        btns['Approve'].pack(side='left', padx=3)
        
        btns['Merge'] = ttk.Button(
            btn_fr, text="Merge",
            command=lambda: self._merge_pr(pr_selected(), owner, repo, headers, tree)
        )
        btns['Merge'].pack(side='left', padx=3)
        
        btns['Req. Changes'] = ttk.Button(
            btn_fr, text="Req. Changes",
            command=lambda: self._pr_action(pr_selected(), 'REQUEST_CHANGES', owner, repo, headers, tree)
        )
        btns['Req. Changes'].pack(side='left', padx=3)
        
        btns['Comment'] = ttk.Button(
            btn_fr, text="Comment",
            command=lambda: self._pr_action(pr_selected(), 'COMMENT', owner, repo, headers, tree)
        )
        btns['Comment'].pack(side='left', padx=9)
        
        ttk.Button(btn_fr, text="Refresh", command=self.refresh).pack(side='left', padx=10)
        ttk.Button(btn_fr, text="Show PR Reviews", command=lambda: self._show_pr_reviews(pr_selected(), owner, repo, headers)).pack(side='left', padx=2)
    
    @threaded
    def _pr_action(self, pr, event_type, owner, repo, headers, tree=None):
        if not pr:
            return
        
        pr_num = pr['number']
        body = ""
        if event_type == "COMMENT":
            body = simple_input("PR Review Comment", "Enter PR review comment:")
            if body is None:
                return
        
        payload = {'event': event_type}
        if body:
            payload['body'] = body
        
        post_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_num}/reviews"
        r = requests.post(post_url, headers=headers, json=payload)
        
        if r.status_code == 200 or r.status_code == 201:
            self.app.set_status(f"{event_type} sent for PR #{pr_num}")
        else:
            self.app.set_status(f"Failed: {r.status_code} {r.text}")
        
        self.refresh()
    
    @threaded
    def _merge_pr(self, pr, owner, repo, headers, tree):
        if not pr:
            return
        
        pr_num = pr['number']
        merge_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_num}/merge"
        r = requests.put(merge_url, headers=headers)
        
        if r.status_code in (200, 201):
            self.app.set_status(f"Merged PR #{pr_num}")
        else:
            try:
                msg = r.json().get('message')
            except Exception:
                msg = r.text
            self.app.set_status(f"Merge failed: {r.status_code} {msg}")
        
        self.refresh()
    
    @threaded
    def _comment_on_issue_or_pr(self, obj, owner, repo, headers, is_pr=False):
        if not obj:
            return
        
        number = obj['number']
        body = simple_input("GitHub Comment", "Type comment to post:")
        if not body:
            return
        
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}/comments"
        resp = requests.post(url, headers=headers, json={"body": body})
        
        if resp.status_code == 201:
            self.app.set_status(f"Comment posted on {'PR' if is_pr else 'issue'} #{number}")
        else:
            self.app.set_status(f"Failed: {resp.status_code} {resp.text}")
        
        self.refresh()
    
    @threaded
    def _show_pr_reviews(self, pr, owner, repo, headers):
        if not pr:
            return
        
        pr_num = pr['number']
        get_url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_num}/reviews"
        r = requests.get(get_url, headers=headers)
        
        if r.status_code == 200:
            reviews = r.json()
            out = []
            for review in reviews:
                out.append(
                    f"{review['user']['login']}: {review['state']} ({review.get('body', '')})"
                )
            msg = "\n".join(out) if out else "No reviews."
            messagebox.showinfo(f"PR #{pr_num} Reviews", msg)
        else:
            messagebox.showerror("Error", f"{r.status_code} {r.text}")
    
    def _display_issues(self, issues, owner, repo, headers):
        frame = self.issue_frame
        for child in frame.winfo_children():
            child.destroy()
        
        columns = ['#', 'Title', 'User', 'State', 'Date']
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse", height=8)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=110 if col != "Title" else 270)
        
        issue_map = {}
        for iss in issues:
            key = iss['number']
            issue_map[key] = iss
            tree.insert('', 'end', iid=str(key), values=[
                f"#{iss['number']}",
                iss['title'][:45],
                iss.get('user', {}).get('login', ''),
                iss['state'],
                iss['created_at'][:10]
            ])
        
        tree.pack(fill='both', expand=True, side='top')
        
        def iss_selected():
            sel = tree.selection()
            if not sel:
                return None
            return issue_map.get(int(sel[0]))
        
        btnrow = ttk.Frame(frame)
        btnrow.pack(anchor='w', padx=7, pady=(2,6))
        
        ttk.Button(btnrow, text="Reply", command=lambda: self._comment_on_issue_or_pr(iss_selected(), owner, repo, headers, is_pr=False)).pack(side='left', padx=3)
        ttk.Button(btnrow, text="Edit", command=lambda: self._edit_issue(iss_selected(), owner, repo, headers)).pack(side='left', padx=3)
        ttk.Button(btnrow, text="Close", command=lambda: self._set_issue_state(iss_selected(), owner, repo, headers, 'closed')).pack(side='left', padx=4)
        ttk.Button(btnrow, text="Reopen", command=lambda: self._set_issue_state(iss_selected(), owner, repo, headers, 'open')).pack(side='left', padx=4)
        ttk.Button(btnrow, text="React", command=lambda: self._react_to_issue(iss_selected(), owner, repo, headers)).pack(side='left', padx=8)
        ttk.Button(btnrow, text="Refresh", command=self.refresh).pack(side='left', padx=7)
    
    @threaded
    def _edit_issue(self, iss, owner, repo, headers):
        if not iss:
            return
        
        number = iss['number']
        title = simple_input("Edit Issue Title", "New title:") or iss['title']
        body = simple_input("Edit Issue Body", "New body:") or iss.get('body', '')
        
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}"
        r = requests.patch(url, headers=headers, json={"title": title, "body": body})
        
        if r.status_code == 200:
            self.app.set_status("Issue edited.")
        else:
            self.app.set_status(f"Edit failed: {r.status_code} {r.text}")
        
        self.refresh()
    
    @threaded
    def _set_issue_state(self, iss, owner, repo, headers, newstate):
        if not iss:
            return
        
        if iss['state'] == newstate:
            self.app.set_status("Issue already in that state.")
            return
        
        number = iss['number']
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}"
        r = requests.patch(url, headers=headers, json={"state": newstate})
        
        if r.status_code == 200:
            self.app.set_status(f"Issue #{number} marked {newstate}")
        else:
            self.app.set_status(f"Failed to update issue: {r.status_code} {r.text}")
        
        self.refresh()
    
    @threaded
    def _react_to_issue(self, iss, owner, repo, headers):
        if not iss:
            return
        
        number = iss['number']
        choose = messagebox.askquestion("React to", "React to (y) Issue or (n) Last Comment?")
        
        if choose == 'yes':
            url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}/reactions"
            target = 'issue'
        else:
            c_url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{number}/comments"
            comments = requests.get(c_url, headers=headers)
            if comments.status_code == 200 and comments.json():
                cid = comments.json()[-1]['id']
                url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/comments/{cid}/reactions"
                target = 'comment'
            else:
                self.app.set_status("No comments to react to!")
                return
        
        emoji = simple_input("Emoji", "Enter :emoji: (e.g., +1, laugh, heart):")
        if not emoji:
            return
        
        react_headers = headers.copy()
        react_headers['Accept'] = 'application/vnd.github.squirrel-girl-preview+json'
        r = requests.post(url, headers=react_headers, json={"content": emoji})
        
        if r.status_code == 201:
            self.app.set_status(f"Reacted to {target}!")
        else:
            self.app.set_status(f"Failed: {r.status_code} {r.text}")
        
        self.refresh()

class GitApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('GitHub Version & Push Tool')
        self.geometry('950x795')
        self.resizable(True, True)
        
        # Instance variables
        self.project_dir = ''
        self.package_json_path = ''
        self.current_branch = tk.StringVar()
        self.current_remote = tk.StringVar()
        self.push_tags = tk.BooleanVar(value=True)
        self.show_output = tk.BooleanVar(value=False)
        self.status = tk.StringVar()
        self.current_version = tk.StringVar()
        self.new_version = tk.StringVar()
        self.commit_msg = tk.StringVar()
        self.repo_url_var = tk.StringVar()
        self.user_var = tk.StringVar()
        self.token_var = tk.StringVar()
        self.advanced_output_shown = False
        self.tag_var = tk.StringVar()
        self.new_tag_var = tk.StringVar()
        
        self.build_ui()
        self.load_keyring_credentials()

    # --- UI ---
    def build_ui(self):
        # Toolbar
        toolbar = ttk.Frame(self, padding="2 4 2 4")
        toolbar.pack(side='top', fill='x')
        
        self.notif_badge = ttk.Label(
            toolbar,
            text="",
            foreground='white',
            background='purple',
            padding=4,
            font=("TkDefaultFont", 9, 'bold')
        )
        self.notif_badge.pack(side='right', padx=8)
        
        ttk.Button(toolbar, text="Choose Folder", command=self.select_folder).pack(side='left', padx=2)
        
        # Notebook with tabs
        self.notebook = ttk.Notebook(self)
        
        self.tab_dashboard = GitHubDashboard(self.notebook, self)
        self.tab_main = ttk.Frame(self.notebook)
        self.tab_settings = ttk.Frame(self.notebook)
        self.tab_help = ttk.Frame(self.notebook)
        
        self.notebook.add(self.tab_dashboard, text="Dashboard")
        self.notebook.add(self.tab_main, text="Version & Push")
        self.notebook.add(self.tab_settings, text="Settings")
        self.notebook.add(self.tab_help, text="Help")
        
        self.notebook.pack(fill='both', expand=True)
        
        # --- Version & Push tab
        f = self.tab_main
        
        ttk.Label(f, text="Current project folder:").pack(anchor='w', padx=24, pady=(14,1))
        self.project_label = ttk.Label(f, text='(None selected)', foreground='blue')
        self.project_label.pack(anchor='w', padx=30, pady=(0,8))
        
        ttk.Label(f, text="Current git branch:").pack(anchor='w', padx=24)
        ttk.Label(f, textvariable=self.current_branch, foreground='blue').pack(anchor='w', padx=30)
        
        ttk.Label(f, text="Current remote URL:").pack(anchor='w', padx=24)
        ttk.Label(f, textvariable=self.current_remote, foreground='blue').pack(anchor='w', padx=30)
        
        row = ttk.Frame(f)
        row.pack(pady=6, fill='x', padx=10)
        ttk.Label(row, text="Set remote to:", width=14).pack(side='left')
        ttk.Entry(row, textvariable=self.repo_url_var, width=56).pack(side='left', padx=2)
        ttk.Button(row, text="Update Remote URL", command=self.update_git_remote_url).pack(side='left', padx=2)
        
        ttk.Label(f, text="Current version:").pack(anchor='w', padx=24, pady=(12,0))
        ttk.Entry(f, textvariable=self.current_version, state='readonly', width=24).pack(padx=30, pady=(0,6))
        
        ttk.Label(f, text="New version:").pack(anchor='w', padx=24)
        ttk.Entry(f, textvariable=self.new_version, width=24).pack(padx=30, pady=(0,8))
        
        ttk.Label(f, text="Commit message:").pack(anchor='w', padx=24)
        
        ttk.Label(f, text="Files to stage/unstage:").pack(anchor='w', padx=24, pady=(12,0))
        self.file_listbox = tk.Listbox(f, selectmode='multiple', width=80, height=7)
        self.file_listbox.pack(padx=30, pady=(0,6))
        
        btn_row = ttk.Frame(f)
        btn_row.pack(anchor='w', padx=32, pady=(0,9))
        ttk.Button(btn_row, text="Stage Selected", command=self.stage_selected).pack(side='left', padx=4)
        ttk.Button(btn_row, text="Unstage Selected", command=self.unstage_selected).pack(side='left', padx=7)
        ttk.Button(btn_row, text="Refresh File List", command=self.refresh_file_list).pack(side='left', padx=7)
        
        ttk.Entry(f, textvariable=self.commit_msg, width=60).pack(padx=30, pady=(0,8))
        
        options = ttk.Frame(f)
        options.pack(fill='x', padx=28, pady=4)
        ttk.Checkbutton(options, text="Push tags?", variable=self.push_tags).pack(side='left')
        ttk.Checkbutton(options, text="Show full git output", variable=self.show_output, command=self.toggle_output).pack(side='left', padx=22)
        ttk.Button(options, text="Clear All Fields", command=self.clear_fields).pack(side='left', padx=15)
        
        sep = ttk.Separator(f, orient='horizontal')
        sep.pack(fill='x', padx=24, pady=12)
        
        ttk.Label(f, text="Tags Management", font=('TkDefaultFont', 10, 'bold')).pack(anchor='w', padx=24)
        
        tagrow = ttk.Frame(f)
        tagrow.pack(anchor='w', padx=32, pady=(2,0))
        ttk.Label(tagrow, text="Tags: ").pack(side='left')
        self.tag_combo = ttk.Combobox(tagrow, textvariable=self.tag_var, width=40, state="readonly")
        self.tag_combo.pack(side='left', padx=6)
        ttk.Button(tagrow, text="Refresh Tags", command=self.load_tags).pack(side='left', padx=6)
        ttk.Button(tagrow, text="Push Selected Tag", command=self.push_tag).pack(side='left', padx=6)
        
        tagrow2 = ttk.Frame(f)
        tagrow2.pack(anchor='w', padx=32, pady=2)
        ttk.Label(tagrow2, text="Create new tag: ").pack(side='left')
        ttk.Entry(tagrow2, textvariable=self.new_tag_var, width=24).pack(side='left', padx=4)
        ttk.Button(tagrow2, text="Create Tag Locally", command=self.create_tag).pack(side='left', padx=6)
        ttk.Button(tagrow2, text="Delete Selected Tag", command=self.delete_tag).pack(side='left', padx=6)
        
        ttk.Button(f, text="Commit Only", command=self.commit_only, width=16).pack(pady=4)
        ttk.Button(f, text="V&P (Version & Push)", command=self.version_and_push, width=24).pack(pady=12)
        
        pull_row = ttk.Frame(f)
        pull_row.pack(anchor='w', padx=32, pady=(0,4))
        ttk.Button(pull_row, text="Pull (merge)", command=self.git_pull).pack(side='left', padx=2)
        ttk.Button(pull_row, text="Pull (rebase)", command=self.git_pull_rebase).pack(side='left', padx=6)
        
        ttk.Label(f, textvariable=self.status, foreground='darkblue').pack(anchor='w', padx=30, pady=1)
        
        self.advframe = ttk.Frame(f)
        self.advframe.pack(fill='both', expand=True, padx=15, pady=7)
        self.advframe.pack_forget()
        
        self.output_box = scrolledtext.ScrolledText(self.advframe, height=12, state='disabled', wrap='word')
        self.output_box.pack(fill='both', expand=True)
        
        ttk.Button(f, text="Show/hide git output", command=self.toggle_output).pack(pady=(0,6))

        # --- Settings Tab
        sf = self.tab_settings
        ttk.Label(sf, text="GitHub Username:").pack(pady=(18,3), anchor='w', padx=20)
        ttk.Entry(sf, textvariable=self.user_var, width=40).pack(padx=22)
        ttk.Label(sf, text="GitHub Token (Personal Access Token):").pack(pady=(12,3), anchor='w', padx=20)
        ttk.Entry(sf, textvariable=self.token_var, show="*", width=40).pack(padx=22)
        ttk.Button(sf, text="Save Credentials", command=self.save_keyring_credentials).pack(pady=12)
        ttk.Button(sf, text="Clear Credentials from Keyring", command=self.clear_keyring_credentials).pack(pady=2)
        ttk.Label(sf, text="Credentials are stored securely using keyring AND also optionally in the global git credential store for command-line operations. Note: git credential store is plain-text.", wraplength=570, foreground="grey").pack(pady=4)
        if not keyring_available:
            ttk.Label(sf, text="WARNING: 'keyring' is not installed; secure credential storage is unavailable.", foreground='red').pack(pady=8)
        
        ttk.Separator(sf, orient='horizontal').pack(fill='x', padx=18, pady=(12,8))
        ttk.Button(sf, text="Create Desktop Shortcut", command=self.create_desktop_shortcut).pack(pady=8)

        # --- Help Tab
        hbox = ttk.Frame(self.tab_help)
        hbox.pack(fill='both', expand=True)
        help_text = (
            "GitHub Version & Push Tool – Ultimate Dashboard\n"
            "---------------------------------------------------\n"
            "• Choose any folder inside your project. The app will scan all subfolders for every package.json!\n"
            "• Use live filter to find and select the exact package.json if you have many.\n"
            "• Instantly manage versioning, tags, committing, pushing. All actions have live feedback.\n"
            "• Visit Dashboard for real-time PRs, issues, and commit review—all with full in-app actions (merge/approve/comment/edit/close/react/etc).\n"
            "• Store credentials in the OS keyring (never on disk), and use your saved token for extra API actions.\n"
            "• All output, status, and errors are visible for support or debugging.\n"
            "• Free for all. Open source. Share and build!\n"
            "How to Update Your Project on GitHub Using This App\n"
            "\n"
            "\n"
            "----------------------------------------------------\n"
            "1. Make changes: Edit, add, or remove files in your project.\n"
            "2. Choose your project: Click 'Choose Folder' and select your directory.\n"
            "   If prompted, pick the correct package.json.\n"
            "3. Stage your changes:\n"
            "   • Click 'Refresh File List' to show changed files.\n"
            "   • Select files to include and click 'Stage Selected'.\n"
            "4. Enter a commit message: Briefly describe your changes in the 'Commit message' field.\n"
            "5. Commit your changes: Click 'Commit Only' to save the changes locally. (They are not uploaded yet!)\n"
            "6. Pull latest online changes:\n"
            "   • Click 'Pull (merge)' OR 'Pull (rebase)' to fetch updates from GitHub before pushing.\n"
            "   • If you see a conflict, resolve it as directed, then stage and commit again.\n"
            "7. Push your changes to GitHub:\n"
            "   • Click 'V&P (Version & Push)' to upload.\n"
            "   • Optionally, enter a new version if releasing an update; otherwise, leave blank.\n"
            "8. Confirm: Visit your GitHub repository online and check your updates.\n"
            "\n"
            "Quick Reference:\n"
            " 1. Edit files locally\n"
            " 2. 'Choose Folder'\n"
            " 3. 'Refresh File List' → select files → 'Stage Selected'\n"
            " 4. Enter commit message → 'Commit Only'\n"
            " 5. 'Pull (merge)' or 'Pull (rebase)'\n"
            " 6. 'V&P (Version & Push)'\n"
            "\n"
            "Tips:\n"
            " - Always commit and pull before pushing.\n"
            " - Use 'Commit Only' as often as you like (for local history) before pushing.\n"
            " - If you get out-of-sync errors, just pull, resolve, then push again.\n"
        )
        
        sct = scrolledtext.ScrolledText(hbox, wrap=tk.WORD, height=20)
        sct.insert(tk.END, help_text)
        sct.config(state='disabled')
        sct.pack(expand=True, fill='both', padx=12, pady=(10,0))

    def commit_only(self):
        if not self.project_dir:
            self.append_output("No project folder selected.")
            return
        
        commit_msg = self.commit_msg.get().strip()
        if not commit_msg:
            self.append_output("Enter a commit message before committing.")
            return
        
        # Stage all selected files (or prompt user if none selected)
        sel = self.file_listbox.curselection()
        files = [self.file_listbox.get(i) for i in sel]
        if not files:
            self.append_output("No files selected to commit.")
            return
        
        cmd = ['git', 'add'] + files
        status = self.run_git_command(cmd)
        if status is not True:
            self.append_output(f"Error: {status}")
            return
        
        # Now commit
        cmd = ['git', 'commit', '-m', commit_msg]
        status = self.run_git_command(cmd)
        if status is not True:
            self.append_output(f"Error: {status}")
        else:
            self.append_output("Files committed, but NOT pushed.")
        self.refresh_file_list()

    def create_desktop_shortcut(self):
        app_name = "GitHub Version & Push Tool"
        exec_cmd = f"python3 {os.path.abspath(sys.argv[0])}"
        icon_path = "/usr/share/icons/hicolor/96x96/apps/python3.png"
        
        desktop_entry = f"""[Desktop Entry]
Type=Application
Name={app_name}
Exec={exec_cmd}
Icon={icon_path}
Terminal=false
Categories=Development;
"""
        
        desktop_file = os.path.expanduser("~/.local/share/applications/git_version_push.desktop")
        with open(desktop_file, "w") as f:
            f.write(desktop_entry)
        os.chmod(desktop_file, 0o755)
        
        self.append_output(f"Shortcut created at {desktop_file}")
        messagebox.showinfo("Shortcut", f"Desktop shortcut created at:\n{desktop_file}")

    def clear_fields(self):
        self.package_json_path = ''
        self.project_dir = ''
        self.current_version.set('')
        self.new_version.set('')
        self.commit_msg.set('')
        self.current_branch.set('')
        self.current_remote.set('')
        self.repo_url_var.set('')
        self.project_label.config(text='(None selected)')
        self.append_output('')
        self.clear_output()
        self.tag_combo['values'] = ()
        self.tag_var.set('')
        self.new_tag_var.set('')

    def select_folder(self):
        self.clear_fields()
        folder = filedialog.askdirectory()
        if not folder:
            return
        
        # Find all package.json files
        candidates = []
        for dirpath, dirnames, filenames in os.walk(folder):
            for name in filenames:
                if name == "package.json":
                    path = os.path.join(dirpath, name)
                    candidates.append(path)
        
        if not candidates:
            self.append_output("No package.json found anywhere under that folder.")
            self.package_json_path = ""
            self.project_label.config(text='(None selected)')
            return
        elif len(candidates) == 1:
            chosen = candidates[0]
        else:
            # Multiple package.json files found, let user choose
            dlg = PackageJsonFinder(self, candidates)
            self.wait_window(dlg)
            if dlg.match:
                chosen = dlg.match
            else:
                self.append_output("No file selected.")
                self.package_json_path = ""
                self.project_label.config(text='(None selected)')
                return
        
        self.package_json_path = chosen
        repo_root = os.path.dirname(self.package_json_path)
        
        # Read version from package.json
        try:
            with open(self.package_json_path) as f:
                data = json.load(f)
                ver = data.get('version', 'unknown')
                self.current_version.set(ver)
        except Exception as ex:
            self.append_output(f"Error reading package.json: {ex}")
            return
        
        self.project_label.config(text=repo_root)
        self.current_branch.set(self.get_branch_name(repo_root) or "Unknown")
        cur_remote = self.get_git_remote_url(repo_root)
        self.current_remote.set(cur_remote or "None set")
        self.repo_url_var.set(cur_remote or "")
        self.project_dir = repo_root
        
        self.append_output(f"package.json: {chosen}\nVersion: {ver}\nBranch: {self.current_branch.get()} Remote: {cur_remote}")
        self.load_tags()
        self.tab_dashboard.refresh()
        self.update_notif_badge()

    def update_notif_badge(self):
        dashboard = self.tab_dashboard
        badge = []
        
        try:
            pr_count = len(dashboard.pr_data) if hasattr(dashboard, 'pr_data') else 0
            if pr_count:
                badge.append(f"{pr_count} PRs")
        except Exception:
            pass
        
        try:
            iss_count = len(dashboard.issue_data) if hasattr(dashboard, 'issue_data') else 0
            if iss_count:
                badge.append(f"{iss_count} Issues")
        except Exception:
            pass
        
        try:
            com_count = len(dashboard.commit_data) if hasattr(dashboard, 'commit_data') else 0
            if com_count:
                badge.append(f"{com_count} Commits")
        except Exception:
            pass
        
        self.notif_badge.config(text=", ".join(badge) if badge else "")

    def refresh_file_list(self):
        try:
            result = subprocess.run(['git', 'status', '--porcelain'], cwd=self.project_dir, capture_output=True, text=True)
            files = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    files.append(line[3:])  # Remove git status prefix
            
            if hasattr(self, 'file_listbox'):
                self.file_listbox.delete(0, tk.END)
                for fname in files:
                    self.file_listbox.insert(tk.END, fname)
        except Exception as ex:
            self.append_output(f"Error listing files: {ex}")

    def git_pull(self):
        status = self.run_git_command(['git', 'pull'])
        if status is not True:
            self.append_output(f"Error: {status}")
        else:
            self.append_output("Pulled from remote (merge).")

    def git_pull_rebase(self):
        status = self.run_git_command(['git', 'pull', '--rebase'])
        if status is not True:
            self.append_output(f"Error: {status}")
        else:
            self.append_output("Pulled from remote (rebase).")

    def stage_selected(self):
        sel = self.file_listbox.curselection()
        files = [self.file_listbox.get(i) for i in sel]
        if not files:
            self.append_output("No files selected to stage.")
            return
        
        cmd = ['git', 'add'] + files
        status = self.run_git_command(cmd)
        if status is not True:
            self.append_output(f"Error: {status}")
        else:
            self.append_output("Files staged.")
        self.refresh_file_list()

    def unstage_selected(self):
        sel = self.file_listbox.curselection()
        files = [self.file_listbox.get(i) for i in sel]
        if not files:
            self.append_output("No files selected to unstage.")
            return
        
        cmd = ['git', 'reset', 'HEAD'] + files
        status = self.run_git_command(cmd)
        if status is not True:
            self.append_output(f"Error: {status}")
        else:
            self.append_output("Files unstaged.")
        self.refresh_file_list()

    def load_tags(self):
        if not self.project_dir:
            self.append_output("Select a project folder first.")
            return
        
        try:
            result = subprocess.run(["git", "tag", "--list"], cwd=self.project_dir, capture_output=True, text=True)
            tags = [t for t in result.stdout.strip().split('\n') if t]
            self.tag_combo["values"] = tags
            if tags:
                self.tag_var.set(tags[-1])  # Select the latest tag
            self.append_output("Tag list refreshed.")
        except Exception as ex:
            self.append_output(f"Failed to get tags: {ex}")

    def create_tag(self):
        tag = self.new_tag_var.get().strip()
        if not tag:
            self.append_output("Enter new tag name.")
            return
        
        try:
            result = subprocess.run(["git", "tag", tag], cwd=self.project_dir, capture_output=True, text=True)
            if result.returncode == 0:
                self.append_output(f"Tag '{tag}' created locally.")
                self.load_tags()
            else:
                self.append_output(f"Failed to create tag: {result.stderr}")
        except Exception as ex:
            self.append_output(f"Error: {ex}")

    def delete_tag(self):
        tag = self.tag_var.get().strip()
        if not tag:
            self.append_output("Select a tag to delete.")
            return
        
        if not messagebox.askyesno("Delete tag?", f"Delete tag '{tag}' locally? This cannot be undone!"):
            return
        
        try:
            result = subprocess.run(["git", "tag", "-d", tag], cwd=self.project_dir, capture_output=True, text=True)
            if result.returncode == 0:
                self.append_output(f"Tag '{tag}' deleted locally.")
                self.load_tags()
            else:
                self.append_output(f"Failed to delete tag: {result.stderr}")
        except Exception as ex:
            self.append_output(f"Error: {ex}")

    def push_tag(self):
        tag = self.tag_var.get().strip()
        if not tag:
            self.append_output("Select a tag to push.")
            return
        
        try:
            result = subprocess.run(["git", "push", "origin", tag], cwd=self.project_dir, capture_output=True, text=True)
            if result.returncode == 0:
                self.append_output(f"Tag '{tag}' pushed to origin.")
            else:
                self.append_output(f"Failed to push tag: {result.stderr}")
        except Exception as ex:
            self.append_output(f"Error: {ex}")

    def get_branch_name(self, repo_dir=None):
        if repo_dir is None:
            repo_dir = self.project_dir
        
        try:
            result = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=repo_dir, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def get_git_remote_url(self, repo_dir=None):
        if repo_dir is None:
            repo_dir = self.project_dir
        
        try:
            result = subprocess.run(['git', 'remote', 'get-url', 'origin'], cwd=repo_dir, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def update_git_remote_url(self):
        new_url = self.repo_url_var.get().strip()
        if not new_url:
            self.append_output("Remote URL field is empty.")
            return
        
        cur_remote = self.get_git_remote_url()
        if cur_remote == new_url:
            self.append_output("Remote already set correctly.")
            return
        
        try:
            result = subprocess.run(['git', 'remote', 'set-url', 'origin', new_url], cwd=self.project_dir, capture_output=True, text=True)
            if result.returncode == 0:
                self.append_output("Remote URL updated.")
                self.current_remote.set(new_url)
            else:
                msg = (result.stderr or "Failed to update remote.").strip()
                self.append_output(f"Error: {msg}")
        except Exception as ex:
            self.append_output(f"Error: {ex}")

    def version_and_push(self):
        self.clear_output()
        if not self.project_dir or not self.package_json_path:
            self.append_output("Select a project folder and package.json first.")
            return
        
        new_ver = self.new_version.get().strip()
        commit_msg = self.commit_msg.get().strip()
        
        if not new_ver or not commit_msg:
            self.append_output("You must enter both the new version and commit message.")
            return
        
        # Update package.json version
        try:
            with open(self.package_json_path, 'r+') as f:
                data = json.load(f)
                old_ver = data.get('version')
                data['version'] = new_ver
                f.seek(0)
                f.write(json.dumps(data, indent=2) + '\n')
                f.truncate()
            
            self.current_version.set(new_ver)
            self.append_output(f"Version updated: {old_ver} → {new_ver}")
        except Exception as ex:
            self.append_output("Failed to update package.json: " + str(ex))
            return
        
        # Git operations
        commands = [
            ['git', 'add', 'package.json'],
            ['git', 'commit', '-m', commit_msg],
            ['git', 'tag', f'v{new_ver}'],
            ['git', 'push']
        ]
        
        if self.push_tags.get():
            commands.append(['git', 'push', '--tags'])
        
        for cmd in commands:
            status = self.run_git_command(cmd)
            if status is not True:
                self.append_output(f"Error: {status}")
                return
        
        self.append_output("Version updated, committed, tagged and pushed successfully!")
        self.load_tags()
        self.tab_dashboard.refresh()
        self.update_notif_badge()
        self.refresh_file_list()

    def run_git_command(self, cmd):
        try:
            result = subprocess.run(cmd, cwd=self.project_dir, capture_output=True, text=True)
            out = (result.stdout or '') + (result.stderr or '')
            
            # Always show output in the text area
            self.output_box['state'] = 'normal'
            self.output_box.insert('end', f"$ {' '.join(cmd)}\n{out}\n")
            self.output_box['state'] = 'disabled'
            self.output_box.see('end')
            
            if result.returncode != 0:
                return out.strip()
            return True
        except Exception as ex:
            return str(ex)

    def toggle_output(self):
        self.advanced_output_shown = not self.advanced_output_shown
        if self.advanced_output_shown:
            self.advframe.pack(fill='both', expand=True, padx=15, pady=7)
        else:
            self.advframe.pack_forget()

    def set_status(self, msg):
        self.status.set(msg)

    def clear_output(self):
        self.output_box['state'] = 'normal'
        self.output_box.delete(1.0, tk.END)
        self.output_box['state'] = 'disabled'

    # --- Keyring + Credential Helper Integration ---
    def save_keyring_credentials(self):
        user = self.user_var.get()
        token = self.token_var.get()
        
        # Save to python keyring, as before
        if not keyring_available:
            messagebox.showerror("Keyring unavailable", "Python 'keyring' package is not installed.")
            return
        
        if user:
            keyring.set_password(SERVICE_NAME, 'github_user', user)
        if token:
            keyring.set_password(SERVICE_NAME, 'github_token', token)
        
        # Also configure git credential.helper store (plain-text, less secure but easy)
        try:
            subprocess.run(["git", "config", "--global", "credential.helper", "store"])
            git_url = f"https://{user}:{token}@github.com"
            
            cred_file = os.path.expanduser("~/.git-credentials")
            already_configured = False
            
            if os.path.exists(cred_file):
                with open(cred_file, "r") as f:
                    lines = f.readlines()
                    for line in lines:
                        if f"https://{user}:" in line and "@github.com" in line:
                            already_configured = True
                            break
            
            if not already_configured:
                with open(cred_file, "a") as f:
                    f.write(git_url + "\n")
            
            self.append_output("Credentials saved to keyring and git credential store (plain-text).")
            messagebox.showinfo("Credentials", "Saved to both keyring and global git credential store.\n\nNote: This stores your token in plain-text in ~/.git-credentials.")
        except Exception as ex:
            self.append_output(f"Error saving to git credential store: {ex}")

    def append_output(self, msg):
        self.output_box['state'] = 'normal'
        self.output_box.insert('end', msg + '\n')
        self.output_box['state'] = 'disabled'
        self.output_box.see('end')

    def clear_keyring_credentials(self):
        if not keyring_available:
            messagebox.showerror("Keyring unavailable", "Python 'keyring' package is not installed.")
            return
        
        try:
            keyring.delete_password(SERVICE_NAME, 'github_user')
        except Exception:
            pass
        
        try:
            keyring.delete_password(SERVICE_NAME, 'github_token')
        except Exception:
            pass
        
        self.user_var.set('')
        self.token_var.set('')
        self.append_output("Credentials erased from keyring.")

    def load_keyring_credentials(self):
        if keyring_available:
            try:
                user = keyring.get_password(SERVICE_NAME, 'github_user')
                token = keyring.get_password(SERVICE_NAME, 'github_token')
                if user:
                    self.user_var.set(user)
                if token:
                    self.token_var.set(token)
            except Exception:
                pass

    def get_token(self):
        if keyring_available:
            try:
                tok = keyring.get_password(SERVICE_NAME, 'github_token')
                return tok or self.token_var.get().strip()
            except Exception:
                pass
        return self.token_var.get().strip()

if __name__ == '__main__':
    app = GitApp()
    app.mainloop()
