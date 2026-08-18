export const conflictInfo = {
  definition: "A merge conflict occurs when Git can't automatically combine changes because the same part of a file was edited differently in two branches.",
  whyHappens: [
    "Same line(s) edited in both branches.",
    "Git doesn't know which change to keep.",
    "You must choose and confirm the correct one.",
  ],
};

export const conflictMarkers = {
  head: "<<<<<<<< HEAD",
  separator: "=========",
  feature: ">>>>>>>> feature-login",
  explanation: [
    { marker: "<<<<<<<< HEAD", meaning: "Changes from your current branch (usually main)." },
    { marker: "=========", meaning: "Separator between the two changes." },
    { marker: ">>>>>>>> feature-login", meaning: "Changes from the branch you are merging in." },
  ],
};

export const exampleConflict = {
  mainBranch: {
    file: "main branch (file: app.js)",
    code: `function login() {
  return "Login Page"; // Older text
}`,
  },
  featureBranch: {
    file: "feature-login branch (file: app.js)",
    code: `function login() {
  return "User Login Page"; // New text
}`,
  },
  conflictResult: `function login() {
<<<<<<< HEAD
  return "Login Page";       // Your current branch (main)
=======
  return "User Login Page";   // Incoming branch (feature-login)
>>>>>>> feature-login
}`,
  resolvedCode: `function login() {
  return "User Login Page";
}`,
};

export const resolutionSteps = [
  {
    step: 1,
    title: "Git Shows Conflict",
    command: "$ git merge feature-login",
    description: "Run the merge command and Git will stop with a conflict.",
  },
  {
    step: 2,
    title: "Open The File",
    command: "$ code app.js",
    description: "Open the file with conflict markers.",
  },
  {
    step: 3,
    title: "Choose The Correct Code",
    command: "",
    description: "Edit the file and keep the right changes. Remove the conflict markers.",
  },
  {
    step: 4,
    title: "Save The File",
    command: "",
    description: "Save the file after resolving the conflict.",
  },
  {
    step: 5,
    title: "Stage The File",
    command: "$ git add app.js",
    description: "Add the resolved file to the staging area.",
  },
  {
    step: 6,
    title: "Complete The Merge",
    command: "$ git commit",
    description: "Commit to finish the merge.",
  },
];

export const quickTips = [
  "Pull latest changes before merging.",
  "Keep changes small and focused.",
  "Communicate with your team.",
  "Use clear commit messages.",
  "Test before resolving conflicts.",
];

export const commonMistakesMerge = [
  "Deleting conflict markers without choosing the right code.",
  "Forgetting to add the resolved file.",
  "Committing before testing.",
  "Ignoring conflicts and pushing.",
];

export const mergeCommandInfo = {
  command: "git merge feature-login",
  whatDoesItDo: [
    "Brings changes from another branch into your current branch.",
    "Combines the commit history.",
    "Creates a merge commit to keep history clear.",
  ],
  whyIsItUseful: [
    "Integrates completed feature work.",
    "Keeps the project up-to-date.",
    "Maintains a clean and complete history for the team.",
  ],
  whenToUse: [
    "When a feature is tested and ready.",
    "When a bug fix is complete.",
    "When merging after code review.",
    "When releasing to production.",
  ],
};

export const mergeWorkflowSteps = [
  { step: 1, icon: "</>", title: "Finish Work", desc: "Complete your work on the feature branch.", command: "" },
  { step: 2, icon: "🔀", title: "Switch to Main", desc: "Always merge into main (or target branch).", command: "$ git switch main" },
  { step: 3, icon: "🔀", title: "Merge Branch", desc: "This combines the changes.", command: "$ git merge feature-login" },
  { step: 4, icon: "✓", title: "Resolve Conflicts", desc: "Fix conflicts if they occur and commit the resolution.", command: "" },
  { step: 5, icon: "☁️", title: "Push Changes", desc: "Share the merged changes with your team.", command: "$ git push origin main" },
];
