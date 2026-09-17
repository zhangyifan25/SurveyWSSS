# How to upload this folder to GitHub

1. Create a new empty repository on GitHub, e.g. `Awesome-WSSS` (do **not** initialize with README).

2. In a terminal:

```bash
cd "/Users/fanbaoyihao/工作/博士文件/论文/论文6_WSSS综述/分类/Awesome-WSSS"
git init
git add README.md LICENSE .gitignore figs _build_readme.py UPLOAD.md
git commit -m "Initial commit: Awesome WSSS survey companion repo"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/Awesome-WSSS.git
git push -u origin main
```

3. After the repo is live, edit `README.md`:
   - Replace paper / arXiv badge URLs
   - Update the BibTeX entry (doi / year)
   - Replace `YOUR_GITHUB_USER/Awesome-WSSS` in the Star History widget

4. (Optional) Regenerate tables after updating `../main.tex` or `../references.bib`:

```bash
python3 _build_readme.py
```

Code links that are still `N/A` can be filled later via Pull Requests.
