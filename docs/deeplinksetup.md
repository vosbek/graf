# Deep Link Setup for Source Citations

This guide explains how to enable one-click deep links from chat citations to your code host (GitHub/GitLab/Bitbucket) and how the UI builds provenance breadcrumbs and line anchors.

## Overview

When the AI chat returns an answer, it includes citations with file-level provenance. Each citation contains:
- repository (e.g., `legacy-user-service`)
- file_path (e.g., `src/main/java/com/acme/auth/LoginAction.java`)
- start_line / end_line (when available)
- score

The frontend renders:
- Breadcrumbs: `repository › file_path:start_line–end_line`
- “View source” link that opens the exact file and line range in your code host

## Required Frontend Environment Variables

Add the following variables to your frontend environment (e.g., `.env` in `frontend/` or your hosting configuration):

```
REACT_APP_GIT_WEB_BASE=https://github.com/your-org
REACT_APP_GIT_DEFAULT_REF=main
```

- REACT_APP_GIT_WEB_BASE:
  - The base URL of your code host organization/group
  - Examples:
    - GitHub: `https://github.com/your-org`
    - GitLab: `https://gitlab.com/your-group`
    - Bitbucket Cloud: `https://bitbucket.org/your-team`
- REACT_APP_GIT_DEFAULT_REF:
  - The default branch or ref (e.g., `main`, `master`, or a fixed release branch)
  - Used to build blob URLs unless a specific commit/ref is provided (optional future enhancement)

After setting these, rebuild the frontend so the environment variables are embedded into the bundle.

## URL Construction

The UI builds deep links for each citation as:

```
{REACT_APP_GIT_WEB_BASE}/{repository}/blob/{REACT_APP_GIT_DEFAULT_REF}/{file_path}#L{start_line}-L{end_line}
```

Examples:
- GitHub:
  ```
  https://github.com/your-org/legacy-user-service/blob/main/src/main/java/.../LoginAction.java#L120-L185
  ```
- GitLab:
  ```
  https://gitlab.com/your-group/legacy-user-service/-/blob/main/src/main/java/.../LoginAction.java#L120-185
  ```
  Note: GitLab anchor style may differ. If needed, adjust anchor building in `buildGitWebUrl()`.

If `start_line` or `end_line` is missing, the link will point to the file without a line-range anchor.

## Where It’s Implemented

- Breadcrumbs and deep links are rendered in:
  - `frontend/src/components/ChatInterface.js`
    - Look for `buildGitWebUrl()` and `CitationItem` to adjust behavior or styling

- Chat citations are populated (with line ranges) by:
  - `strands/agents/chat_agent.py` (citations assembly)
  - Line range metadata comes from Chroma metadata:
    - `src/core/chromadb_client.py` → `_prepare_metadata()` includes `start_line` and `end_line` if available

## Optional Enhancements

1) Include Commit/Ref per Citation
   - Extend the indexer to capture a repository commit/ref at index time and store it in Chroma metadata (e.g., `repo_ref`)
   - Update the chat agent to pass `repo_ref` in citations
   - Update `buildGitWebUrl()` to prefer `repo_ref` over `REACT_APP_GIT_DEFAULT_REF`

2) Local Repository Browser
   - If you have a local RepositoryBrowser view, detect when `REACT_APP_GIT_WEB_BASE` is unset and fallback to a local route that opens the file and scrolls to the line range
   - Optionally support multi-tenant source roots for monorepos

3) IDE Jump (Developer Mode)
   - Provide a developer-only deep link using VS Code protocol:
     - `vscode://file/<absolute-path>:<line>`
   - Gate behind a user setting to avoid accidental exposure

## Troubleshooting

- Links do not appear
  - Ensure `REACT_APP_GIT_WEB_BASE` is set and the frontend was rebuilt after changes
- Linking to wrong branch
  - Update `REACT_APP_GIT_DEFAULT_REF` or implement per-citation commit/ref capture
- No line anchors
  - Verify that `start_line` and `end_line` exist in citations; check indexing to ensure chunk metadata includes these fields

## Security Considerations

- Ensure your code host URLs are accessible only to authorized users
- Do not expose internal repository names or paths to unauthorized clients
- If running behind SSO, ensure the browser session is authenticated before expecting deep links to work

---

With these settings in place, users can click from chat answers directly to the exact lines of referenced code, speeding verification, review, and migration planning.