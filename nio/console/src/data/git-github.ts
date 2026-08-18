export interface GitCommand {
  command: string;
  description: string;
}

export const gitBasics: GitCommand[] = [
  { command: "git --version", description: "Check Git version" },
  { command: 'git config --global user.name "Your Name"', description: "Set your name" },
  { command: 'git config --global user.email "you@example.com"', description: "Set your email" },
  { command: "git init", description: "Initialize a new Git repository" },
  { command: "git clone <repo_url>", description: "Clone a repository" },
  { command: "git status", description: "Check status of changes" },
  { command: "git add <file>", description: "Stage a specific file" },
  { command: "git add .", description: "Stage all changes" },
  { command: 'git commit -m "message"', description: "Commit staged changes" },
  { command: "git log", description: "View commit history" },
  { command: "git diff", description: "Show changes not staged" },
  { command: "git diff --staged", description: "Show changes staged" },
  { command: "git remote -v", description: "Show remote repositories" },
  { command: "git push", description: "Push changes to remote" },
  { command: "git pull", description: "Pull changes from remote" },
  { command: "git fetch", description: "Fetch changes from remote" },
  { command: "git branch", description: "List all branches" },
  { command: "git branch <branch_name>", description: "Create a new branch" },
  { command: "git checkout <branch_name>", description: "Switch to a branch" },
  { command: "git checkout -b <branch_name>", description: "Create and switch to new branch" },
  { command: "git merge <branch_name>", description: "Merge a branch into current" },
  { command: "git branch -d <branch_name>", description: "Delete a branch" },
];

export const undoCommands: GitCommand[] = [
  { command: "git checkout -- <file>", description: "Discard changes in working directory" },
  { command: "git reset HEAD <file>", description: "Unstage file, keep modifications" },
  { command: "git reset --hard", description: "Discard all changes" },
  { command: "git revert <file>", description: "Undo a commit" },
];

export const stashCommands: GitCommand[] = [
  { command: "git stash", description: "Stash changes temporarily" },
  { command: "git stash list", description: "List all stashes" },
  { command: "git stash pop", description: "Apply stash and remove it" },
  { command: "git stash drop", description: "Delete a stash" },
];

export const tagCommands: GitCommand[] = [
  { command: "git tag", description: "List all tags" },
  { command: "git tag -a <tag_name>", description: "Create annotated tag" },
  { command: "git push origin <tag_name>", description: "Push a tag" },
  { command: "git tag -d <tag_name>", description: "Delete a tag" },
];

export const remoteCommands: GitCommand[] = [
  { command: "git remote add origin <url>", description: "Add a remote repo" },
  { command: "git remote remove origin", description: "Remove remote repo" },
  { command: "git push -u origin <branch>", description: "Push and set upstream" },
  { command: "git pull origin <branch>", description: "Pull from specific branch" },
];

export const viewSearchCommands: GitCommand[] = [
  { command: "git log --oneline --graph --all", description: "Compact commit history" },
  { command: "git blame <file>", description: "Show who changed each line" },
  { command: 'git show <commit_id>', description: "Show details of a commit" },
  { command: 'git grep -n "text"', description: "Search text in repository" },
  { command: "git log --grep='text'", description: "Search commits by message" },
  { command: "git diff HEAD~1", description: "Show diff with previous commit" },
  { command: "git branch --merged", description: "List merged branches" },
  { command: "git branch --no-merged", description: "List unmerged branches" },
];

export const githubEssentials = [
  {
    name: "Repository (Repo)",
    icon: "📁",
    description: "A project folder where all your files and history live.",
  },
  {
    name: "Fork",
    icon: "🍴",
    description: "A copy of someone else's repository under your GitHub account.",
  },
  {
    name: "Clone",
    icon: "📥",
    description: "Copy a repository from GitHub to your local machine.",
  },
  {
    name: "Pull Request (PR)",
    icon: "🔄",
    description: "Propose your changes and request them to be merged into the main repository.",
  },
  {
    name: "Issue",
    icon: "🐛",
    description: "Track bugs, tasks, or feature requests in a repository.",
  },
  {
    name: "Actions",
    icon: "⚡",
    description: "Automate workflows like testing, deployment, and CI/CD.",
  },
  {
    name: "Projects",
    icon: "📋",
    description: "Organize tasks, sprints, and progress visually.",
  },
  {
    name: "Wiki",
    icon: "📖",
    description: "Add documentation and knowledge base to your repository.",
  },
  {
    name: "Stars",
    icon: "⭐",
    description: "Show appreciation for projects you find useful.",
  },
  {
    name: "Watch",
    icon: "👁️",
    description: "Stay updated on a repository's activities.",
  },
];

export const workflows = [
  {
    title: "Basic Workflow",
    steps: ["Make Changes", "Stage Changes", "Commit Changes", "Push to GitHub"],
  },
  {
    title: "Branching Workflow",
    steps: ["Create Branch", "Make & Commit Changes", "Merge Branch", "Push to GitHub"],
  },
  {
    title: "Fork & Pull Request Workflow",
    steps: ["Fork Repository", "Make Changes in Your Fork", "Create Pull Request", "Review & Merge"],
  },
];

export const bestPractices = [
  "Write meaningful commit messages",
  "Pull before you push",
  "Use branches for new features or fixes",
  "Keep your repository clean and organized",
  "Review code before merging",
  "Use .gitignore to avoid unnecessary files",
  "Document your project with a README",
];
