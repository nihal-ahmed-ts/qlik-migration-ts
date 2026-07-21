# CI workflow (pending relocation)

`ci/validate.yml` is the GitHub Actions workflow for this repo (validators +
unit tests + offline smoke tests on every PR and push to `main`).

It lives here rather than in `.github/workflows/` because the Personal Access
Token used to open the restructure PR lacks the `workflow` scope, which GitHub
requires to add or modify files under `.github/workflows/`.

**To activate CI**, move it into place with a token that has `workflow` scope
(or via the GitHub web UI):

```bash
mkdir -p .github/workflows
git mv ci/validate.yml .github/workflows/validate.yml
git commit -m "ci: activate validate workflow" && git push
```
